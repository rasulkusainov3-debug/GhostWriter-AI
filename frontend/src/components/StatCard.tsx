type Props = {
  label: string;
  value: string | number;
  accent?: 'teal' | 'coral' | 'grape' | 'amber';
};

const colors = {
  teal: 'border-teal/30 bg-teal/10',
  coral: 'border-coral/30 bg-coral/10',
  grape: 'border-grape/30 bg-grape/10',
  amber: 'border-amber/40 bg-amber/20',
};

export function StatCard({ label, value, accent = 'teal' }: Props) {
  return (
    <div className={`stat-card panel border ${colors[accent]}`}>
      <div className="stat-card__label">{label}</div>
      <div className="stat-card__value">{value}</div>
    </div>
  );
}
