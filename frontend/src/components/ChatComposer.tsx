import { FormEvent } from "react";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  disabled: boolean;
}

export function ChatComposer({ value, onChange, onSubmit, disabled }: Props) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(value);
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label className="sr-only" htmlFor="chat-input">
        Ask GitaGPT
      </label>
      <textarea
        id="chat-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Ask about duty, anger, devotion, focus, or daily life..."
        disabled={disabled}
        rows={2}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        {disabled ? "Asking" : "Ask"}
      </button>
    </form>
  );
}
