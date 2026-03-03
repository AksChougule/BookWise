type StoredBadgeProps = {
  stored: boolean | null;
};

export function StoredBadge({ stored }: StoredBadgeProps) {
  if (stored === null) {
    return null;
  }

  return (
    <span className={`stored-badge ${stored ? "stored-badge--stored" : "stored-badge--generated"}`}>
      {stored ? "Stored" : "Generated"}
    </span>
  );
}
