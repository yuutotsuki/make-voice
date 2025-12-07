import { initializeEnvironment } from '../config/environment';
import OpenAI from 'openai';
import { fetchConnectToken } from '../services/tokenService';
import { getMcpTool } from '../getMcpTool';

initializeEnvironment();

async function main() {
  const token = await fetchConnectToken();
  const gmailTool = getMcpTool('gmail', token);
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

  const prompt = '次の内容で Gmail の下書きを作成してください。JSONの to, subject, body だけに値を入れて、gmail-create-draft ツールを使ってください。\n' +
    'to = example@example.com\n' +
    'subject = テスト下書き\n' +
    'body = これは API 経由で作成したテスト下書きです。';

  const resp = await client.responses.create({
    model: process.env.RESPONSES_MODEL_AUTODRAFT || 'gpt-4.1-mini',
    input: [
      { role: 'system', content: 'You must call the gmail-create-draft tool exactly once, providing JSON arguments with to, subject, body.' },
      { role: 'user', content: prompt }
    ],
    tools: [gmailTool],
    tool_choice: { type: 'tool', name: 'gmail-create-draft' },
    max_output_tokens: 200,
    temperature: 0,
  });

  console.dir(resp?.output, { depth: null });
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
