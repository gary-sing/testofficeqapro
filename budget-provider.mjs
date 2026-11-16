import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const results = path.join(root, 'results');
fs.mkdirSync(results, { recursive: true });
const ledgerPath = path.join(results, 'pilot-ledger.jsonl');
const limit = 20;
const maxOutput = 8192;

export default class BudgetProvider {
  constructor(options) { this.config = options.config; }
  id() { return this.config.model; }
  async callApi(prompt, context) {
    const { model, vendor, inputRate, outputRate } = this.config;
    const ledger = fs.existsSync(ledgerPath)
      ? fs.readFileSync(ledgerPath, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
    const uid = context.test?.metadata?.uid ?? context.vars?.question;
    const previous = ledger.find(row => row.type === 'result' && row.model === model && row.uid === uid && !row.truncated && row.output);
    if (previous) return {output: previous.output, cost: previous.cost, metadata: {reused: true}};
    if (ledger.some(row => row.type === 'error' && row.model === model && row.fatal)) {
      return {error: `${model}: prior account error; request skipped`};
    }
    const committed = ledger.filter(row => row.type === 'reserve').reduce((sum, row) => sum + row.amount, 0);
    // Reserve the UTF-8 byte count as a conservative input-token upper bound.
    // Reservations are never released, even for failures, retries or timeouts.
    const reserve = ((Buffer.byteLength(prompt, 'utf8') + 4096) * inputRate + maxOutput * outputRate) / 1e6;
    if (committed + reserve > limit) return { error: 'Pilot budget reservation limit reached' };
    fs.appendFileSync(ledgerPath, JSON.stringify({type: 'reserve', model, uid, amount: reserve}) + '\n');
    const anthropic = vendor === 'anthropic';
    const headers = anthropic
      ? {'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01'}
      : {Authorization: `Bearer ${process.env.OPENAI_API_KEY}`};
    const body = anthropic
      ? {model, max_tokens: maxOutput, messages: [{role: 'user', content: prompt}], thinking: {type: 'adaptive'}}
      : {model, input: prompt, max_output_tokens: maxOutput, reasoning: {effort: 'medium'}};
    const start = Date.now();
    try {
      const response = await fetch(anthropic ? 'https://api.anthropic.com/v1/messages' : 'https://api.openai.com/v1/responses', {
        method: 'POST', headers: {...headers, 'Content-Type': 'application/json'},
        body: JSON.stringify(body), signal: AbortSignal.timeout(240000),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const error = `${model}: HTTP ${response.status}, ${payload.error?.type ?? 'request failed'}`;
        const fatal = response.status === 401 || response.status === 403 || payload.error?.code === 'insufficient_quota' || payload.error?.type === 'invalid_request_error';
        fs.appendFileSync(ledgerPath, JSON.stringify({type: 'error', model, uid, error, fatal}) + '\n');
        return {error};
      }
      const data = await response.json();
      const usage = data.usage;
      if (!usage) throw Error('Missing usage; cost cannot be measured');
      const input = usage.input_tokens;
      const outputTokens = usage.output_tokens;
      // Caching is not requested. Bill all input at uncached rates conservatively.
      const inputTotal = input + (usage.cache_read_input_tokens ?? 0) + (usage.cache_creation_input_tokens ?? 0);
      const cost = (inputTotal * inputRate + outputTokens * outputRate) / 1e6;
      const output = anthropic
        ? data.content.filter(part => part.type === 'text').map(part => part.text).join('\n')
        : data.output.flatMap(item => item.content ?? []).filter(part => part.type === 'output_text').map(part => part.text).join('\n');
      const latencyMs = Date.now() - start;
      const truncated = anthropic ? data.stop_reason === 'max_tokens' : data.status === 'incomplete';
      fs.appendFileSync(ledgerPath, JSON.stringify({type: 'result', model, uid, cost, inputTokens: inputTotal, outputTokens, latencyMs, truncated, output, usage}) + '\n');
      return {output, cost, tokenUsage: {prompt: inputTotal, completion: outputTokens, total: inputTotal + outputTokens}, metadata: {truncated}};
    } catch (error) {
      fs.appendFileSync(ledgerPath, JSON.stringify({type: 'error', model, uid, error: error.name}) + '\n');
      return {error: `${model}: ${error.name}; reservation retained`};
    }
  }
}
