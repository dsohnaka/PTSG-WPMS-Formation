# Contributing / 貢献について

Contributions to this repository are welcome — but the contribution model differs from a conventional open-source project. This is an Open Prompt repository, and the rules reflect its three-layer structure.

このリポジトリへの貢献を歓迎します——ただし、貢献モデルは従来のオープンソースプロジェクトとは異なります。これはオープンプロンプトリポジトリであり、ルールはその3層構造を反映しています。

---

## What you can contribute / 貢献できるもの

### Layer 1 (Architecture) — Welcome / 第1層（アーキテクチャ）— 歓迎

- Clarifications of existing specifications / 既存仕様の明確化
- Additional mathematical derivations / 追加の数学的導出
- Translations into other languages / 他言語への翻訳
- Cross-references between sections / セクション間の相互参照
- Corrections of errors / 誤りの訂正

Submit via pull request. Contributed Layer 1 material is automatically released into the public domain (CC0) by the act of submission.

プルリクエストで提出してください。提出された第1層素材は、提出行為により自動的にパブリックドメイン (CC0) に公開されます。

### Layer 2 (Reasoning Traces) — Welcome / 第2層（推論軌跡）— 歓迎

- **Your own design dialogues** related to this architecture, with your own LLM collaborator or with other engineers / 本アーキテクチャに関連する、あなた自身の LLM 協働者や他のエンジニアとの**自身の設計対話**
- Critiques and alternative reasoning paths / 批評と代替推論経路
- Educational walkthroughs / 教育的解説
- Translations of existing traces / 既存軌跡の翻訳

Layer 2 contributions are added under your name in `02_Reasoning_Traces/contributed/`. They are also released as CC0 by submission, but your authorship is preserved in the metadata.

第2層への貢献は `02_Reasoning_Traces/contributed/` の下にあなたの名前で追加されます。提出により CC0 として公開されますが、メタデータにあなたの著者性が保持されます。

### Layer 3 (Sample Implementations) — By Discussion / 第3層（サンプル実装）— 議論を経て

Direct contributions to the *original author's* sample implementations are accepted only by prior discussion (open an issue first). The reason: Layer 3 is the original author's reference implementation. We do not want it to gradually become a community-merged codebase, because that would obscure the Open Prompt principle that **regenerated implementations are independent works, not derivatives**.

*オリジナル著者の*サンプル実装への直接貢献は、事前議論（まず Issue を開いてください）を経た場合のみ受け入れられます。理由：第3層はオリジナル著者のリファレンス実装です。これがコミュニティでマージされたコードベースに徐々になることは望ましくありません——なぜなら、それは**再生成された実装は独立した著作物であり派生物ではない**というオープンプロンプトの原理を曖昧にしてしまうからです。

**If you have built your own implementation from this architecture**, the recommended path is **not** to merge it here, but to publish your own Open Prompt repository and link to it from a discussion thread.

**本アーキテクチャから自身の実装を構築した場合**、推奨される経路は、ここにマージすることでは**なく**、自身のオープンプロンプトリポジトリを公開し、議論スレッドからリンクすることです。

---

## How to contribute / 貢献の手順

### For Layer 1 / 第1層

1. Open an issue describing what you propose to add or change / 追加・変更を提案する内容を記述した Issue を開く
2. Submit a pull request with the change / 変更を含むプルリクエストを提出
3. The maintainer will review for technical correctness and integration / メンテナが技術的正確性と統合性をレビュー
4. On merge, your contribution becomes part of the public-domain commons / マージ時、あなたの貢献はパブリックドメインの共有財産の一部となる

### For Layer 2 / 第2層

1. Prepare your dialogue in both Markdown (human-readable) and JSON (LLM-ingestible) formats. See existing files in `02_Reasoning_Traces/` for the format. / 対話を Markdown（人間可読）と JSON（LLM 取り込み可能）の両形式で準備する。形式については `02_Reasoning_Traces/` の既存ファイルを参照
2. Submit a pull request adding your files to `02_Reasoning_Traces/contributed/[your-name]/` / `02_Reasoning_Traces/contributed/[あなたの名前]/` にファイルを追加するプルリクエストを提出
3. Include a metadata header in your Markdown file with date, participants (you + your LLM collaborator's model name and version, if applicable), and topic / 日付、参加者（あなた + あなたの LLM 協働者のモデル名とバージョン、該当する場合）、トピックを含むメタデータヘッダを Markdown ファイルに含める

### For Layer 3 / 第3層

Open an issue first. We will discuss whether the contribution belongs in the original author's reference implementation or whether it should become its own Open Prompt repository.

まず Issue を開いてください。貢献がオリジナル著者のリファレンス実装に属するか、独自のオープンプロンプトリポジトリとなるべきかを議論します。

---

## Layer 2 Quality Guide — The `decision_points` discipline
## 第2層の品質ガイド — `decision_points` の作法

The single most important field in a Layer 2 trace is `decision_points`. This is what distinguishes a Layer 2 reasoning trace from an ordinary chat log or brainstorm transcript. **Decision points are what make a dialogue resumable by another engineer + LLM in the future.**

第2層軌跡で最も重要なフィールドは `decision_points` です。これこそが、第2層の推論軌跡を、ありふれたチャットログやブレインストーミングの書き起こしから区別するものです。**決定ポイントこそが、対話を未来のエンジニア + LLM が再開可能なものにする**のです。

The recommended structure for each decision point is:

各決定ポイントの推奨構造は次のとおりです：

```json
{
  "point": "What was being decided (concise label)",
  "alternatives": ["option A", "option B", "option C"],
  "chosen": "the option chosen, OR 'tie' / 'left in the arena'",
  "rationale": "Why this choice — including what was traded away. Be specific about quantities (bits, ns, MHz, %) wherever possible."
}
```

### Worked example — fixed-point format / 具体例：固定小数点フォーマット

```json
{
  "point": "Fixed-point format for ft input",
  "alternatives": ["Q2.30", "Q3.29", "Q1.31"],
  "chosen": "Q2.30",
  "rationale": "ft の最大値 2π ≈ 6.28 を表現するには整数部に2ビット必要(符号 + 値)。残り30ビットを小数部に割り当てると0.001 Hz分解能を満たせる。Q1.31 は精度が高いがレンジ不足、Q3.29 はレンジ過剰で精度を1ビット失う。"
}
```

This format gives a future reader (human or LLM) everything they need to either accept the decision or revisit it under different constraints. **It records what was traded away, not just what was chosen.**

このフォーマットは、未来の読者（人間または LLM）が、決定を受け入れるか異なる制約のもとで再検討するかに必要なすべてを与えます。**選択されたものだけでなく、何が犠牲になったかを記録する**のがポイントです。

---

## The "Tie" Convention — Preserving Choices for the Arena
## 「引き分け」の作法 — アリーナのために選択を保存する

A Layer 2 trace **does not need to settle every question**. In fact, leaving certain trade-offs explicitly unresolved — declaring a "tie" — is one of the most valuable things a contributor can do.

第2層の軌跡は**すべての問いに決着をつける必要はありません**。それどころか、特定のトレードオフを意図的に未解決のままにする——「引き分け」を宣言する——ことは、貢献者が行える最も価値ある行為の一つです。

When two implementation strategies offer comparable merit but optimize for different constraints, the right move is often *not* to pick one as the winner, but to record both with their respective trade-offs and leave the choice to whoever regenerates the implementation under their own specific constraints.

二つの実装戦略が同等の価値を持ちながら異なる制約に最適化している場合、正しい一手はしばしば一つを勝者として選ぶことでは*なく*、両者を各々のトレードオフとともに記録し、各自の固有の制約の下で実装を再生成する者に選択を委ねることです。

### Worked example — Horner pipeline trade-off / 具体例：Hornerパイプラインのトレードオフ

```json
{
  "point": "Pipeline structure for refactored Horner with absorbed (2π)^2",
  "alternatives": [
    {
      "label": "Approach A — Textbook Horner",
      "latency": "1 clock per stage",
      "precision": "28-bit fractional in 36-bit datapath",
      "tradeoff": "Lower precision but lower latency"
    },
    {
      "label": "Approach B — High-precision refactored Horner",
      "latency": "2 clocks per stage (~80 ns overhead at 100 MHz over 11 stages)",
      "precision": "+4 bits fractional (dynamic range compressed 13×)",
      "tradeoff": "Higher precision but higher latency"
    }
  ],
  "chosen": "tie — left in the Implementation Arena",
  "rationale": "Both options are valid for the architectural specification. The choice depends on the regenerator's constraints: latency-critical applications (active sensing, control loops) favor A; precision-critical applications (fine spectral analysis, audio mastering) favor B. Recording both preserves the design space for future implementers."
}
```

When you declare a tie, do so explicitly. Future readers (human and LLM) will treat ties as **invitations to deepen the dialogue**, not gaps in your reasoning.

引き分けを宣言する際は、明示的にそうしてください。未来の読者（人間と LLM）は、引き分けをあなたの推論の欠落としてではなく、**対話を深めるための招待**として扱います。

---

## Resumption hooks — leaving the door open for future dialogue
## 再開フック — 未来の対話のために扉を開けておく

Each Layer 2 trace should end with a `resumption_hooks` section. These are explicit starting questions that a future reader can use to resume the dialogue with their own LLM. Each hook should be:

各第2層軌跡は `resumption_hooks` セクションで終わるべきです。これらは未来の読者が自身の LLM との対話を再開するために用いる明示的な開始質問です。各フックは以下を満たすべきです：

- **Specific** — refer to a concrete underdeveloped point in the trace, not "explore further" / **具体的** — 軌跡内の具体的な未発展点を指す
- **Actionable** — phrased as a question that has a thinkable answer / **行動可能** — 考え得る答えがある問いとして表現する
- **Bounded** — addresses one issue, not a sprawling topic / **限定的** — 一つの論点を扱い、広範なトピックではない

### Example resumption hook / 再開フック例

```json
{
  "hook_id": "A2",
  "description": "Assuming an AI agent is dynamically generating the Verilog for the Horner pipeline, what specific pragmas or parameters should be passed to the generator to let it choose between Approach A (Low Latency) and Approach B (High Precision)? What runtime conditions would justify each?"
}
```

A trace with three good resumption hooks is far more valuable than a trace that "covers everything." **Coverage is the wrong goal; resumability is the right goal.**

良い再開フックを3つ持つ軌跡は、「すべてをカバーする」軌跡よりはるかに価値があります。**カバレッジは誤った目標であり、再開可能性こそが正しい目標です。**

---

## Multi-AI dialogue traces / 複数AIとの対話軌跡

If your dialogue involved more than one language model — for example, comparing how Claude and Gemini approached the same design question — record this explicitly in the metadata. Multi-AI dialogues are particularly valuable Layer 2 contributions because they show the same problem from different reasoning architectures.

対話に複数の言語モデルが関わった場合——例えば Claude と Gemini が同じ設計問題にどう取り組んだかを比較した場合——これをメタデータに明示的に記録してください。複数 AI との対話は、同じ問題を異なる推論アーキテクチャから示すため、特に価値ある第2層貢献です。

```json
"participants": [
  { "name": "Tsuneo Ohnaka", "role": "FPGA Architect" },
  { "name": "Claude", "provider": "Anthropic", "role": "AI collaborator (architecture/strategy)" },
  { "name": "Gemini", "provider": "Google", "role": "AI collaborator (numerical analysis)" }
]
```

When the same question gets meaningfully different framings from different LLMs, that divergence itself is information worth preserving.

同じ質問が異なる LLM から意味のある異なる枠組みを得る時、その分岐そのものが保存に値する情報です。

---

## Common pitfalls to avoid / 避けるべき一般的な落とし穴

1. **Verbatim transcripts without curation** — A pure dump of every word said is harder to use, not easier. Curate to extract decisions and reasoning. / **キュレーションのない逐語記録** — 言われたすべての言葉のダンプは、使いやすくなるどころか使いにくくなる。決定と推論を抽出するためにキュレーションする
2. **Decisions without rationale** — "We chose X" with no explanation cannot be reconsidered. Always record why. / **根拠なき決定** — 説明のない「Xを選んだ」は再検討できない。常に「なぜ」を記録する
3. **Hidden alternatives** — If you considered an option and rejected it, name it. Future readers may face new constraints under which the rejected option becomes correct. / **隠された選択肢** — 検討して却下した選択肢があれば名指しする。未来の読者は、却下された選択肢が正しくなる新しい制約に直面するかもしれない
4. **Markdown without JSON, or JSON without Markdown** — Both formats are required. Markdown for humans, JSON for LLMs. They are not redundant; they serve different readers. / **JSON なしの Markdown、または Markdown なしの JSON** — 両形式が必須。Markdown は人間のため、JSON は LLM のため。これらは冗長ではない。異なる読者に奉仕する
5. **No resumption hooks** — A trace without resumption hooks is a tomb, not a launching pad. Always leave 2–5 explicit starting questions. / **再開フックなし** — 再開フックのない軌跡は墓場であり、発射台ではない。常に2〜5の明示的な開始質問を残す

---

## Code of conduct / 行動規範

Be respectful, technically rigorous, and intellectually honest. Disagree about ideas, not people. Engage with the strongest version of others' arguments.

敬意を持ち、技術的に厳密に、知的に誠実に。アイデアについて意見を異にし、人について意見を異にしないこと。他者の主張の最強の版に応答すること。

---

## Questions / 質問

Open an issue with the `question` label, or contact the maintainer via the Hackaday.io project page.

`question` ラベル付きの Issue を開くか、Hackaday.io プロジェクトページからメンテナに連絡してください。
