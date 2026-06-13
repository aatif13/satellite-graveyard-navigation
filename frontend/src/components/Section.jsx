export default function Section({ title, icon: Icon, children, accent = false }) {
  return (
    <section className={`panel-section ${accent ? 'panel-section--highlight' : ''}`}>
      {title && (
        <div className="panel-section-head">
          {Icon && <Icon size={15} strokeWidth={1.75} />}
          <span>{title}</span>
        </div>
      )}
      <div className="panel-section-body">{children}</div>
    </section>
  );
}
