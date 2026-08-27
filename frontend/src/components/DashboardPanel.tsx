interface DashboardPanelProps {
  src: string;
}

export function DashboardPanel({ src }: DashboardPanelProps) {
  return (
    <div className="dashboard-panel">
      <div className="dashboard-panel__card">
        <iframe
          key={src}
          src={src}
          title="Dashboard"
          sandbox="allow-scripts"
          className="dashboard-panel__frame"
        />
      </div>
    </div>
  );
}
