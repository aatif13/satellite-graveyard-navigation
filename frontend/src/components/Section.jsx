export default function Section({ title, icon: Icon, children, accent = false }) {
  return (
    <section className={`card-3d ${accent ? 'card-3d-accent' : ''}`}>
      {title && (
        <div className="card-label">
          {Icon && <Icon size={14} className="text-cyan-500" />}
          <span>{title}</span>
        </div>
      )}
      {children}
    </section>
  );
}
