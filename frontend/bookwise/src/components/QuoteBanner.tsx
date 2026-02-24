import { useMemo } from "react";

const quotes = [
  "Read deeply. Think clearly. Act deliberately.",
  "Great books sharpen judgment, not just memory.",
  "A chapter a day compounds into uncommon insight.",
  "Learning sticks when ideas become actions.",
  "Clarity begins with better questions.",
  "Books compress decades into an afternoon.",
  "Understanding beats information overload.",
  "Read to reason, not just to agree.",
  "The best notes are the ones you revisit.",
  "Knowledge grows when reflection is scheduled.",
  "Strong thinking is built from first principles.",
  "Good readers become better decision-makers.",
];

export function QuoteBanner() {
  const quote = useMemo(() => quotes[Math.floor(Math.random() * quotes.length)] ?? quotes[0], []);

  return (
    <section className="rounded-xl border border-app bg-surface p-6">
      <p className="text-sm font-medium text-secondary">Quote of the moment</p>
      <p className="mt-2 text-lg text-primary">“{quote}”</p>
    </section>
  );
}
