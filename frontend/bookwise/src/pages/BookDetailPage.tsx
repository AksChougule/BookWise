import { useParams } from "react-router-dom";

export default function BookDetailPage() {
  const { workId } = useParams();

  return (
    <section className="space-y-3 rounded-xl border border-app bg-surface p-6">
      <h1 className="text-2xl font-semibold">Book Detail</h1>
      <p className="text-secondary">Book detail UI is coming next chunk.</p>
      <p className="text-sm text-secondary">workId: {workId ?? "(missing)"}</p>
    </section>
  );
}
