interface Props {
  prompts: string[];
  onPick: (prompt: string) => void;
}

export function EmptyState({ prompts, onPick }: Props) {
  return (
    <section className="empty-state">
      <p className="eyebrow">Start with a real question</p>
      <h2>Ask, read the answer, then verify the source.</h2>
      <div className="prompt-grid">
        {prompts.map((prompt) => (
          <button key={prompt} onClick={() => onPick(prompt)}>
            {prompt}
          </button>
        ))}
      </div>
    </section>
  );
}
