import sys

with open("dashboard/client/src/App.tsx", "r") as f:
    content = f.read()

# Add Demo to Views
if '"demo"' not in content:
    content = content.replace(
        'type View = "command" | "students" | "attendance" | "history" | "analytics" | "control" | "events";',
        'type View = "command" | "students" | "attendance" | "history" | "analytics" | "control" | "events" | "demo";'
    )
    
    content = content.replace(
        '{ key: "events", label: "System Events", icon: FileText, description: "Operational audit log" },',
        '{ key: "events", label: "System Events", icon: FileText, description: "Operational audit log" },\n  { key: "demo", label: "Demo & Simulation", icon: Zap, description: "Mock hardware operations" },'
    )
    
    content = content.replace(
        '<Route path="/events" component={() => <Events events={events} />} />',
        '<Route path="/events" component={() => <Events events={events} />} /><Route path="/demo" component={() => <DemoSimulation />} />'
    )
    
    demo_component = """
function DemoSimulation() {
  const [studentId, setStudentId] = useState("");
  const simulate = async (endpoint: string, method: string = "POST") => {
    try {
      await api(`/api/system/${endpoint}`, { method });
      toast.success(`Simulated ${endpoint} successfully`);
    } catch (err: any) {
      toast.error(err.message || "Simulation failed");
    }
  };
  return <div className="mx-auto max-w-[1100px] animate-enter">
    <SectionTitle eyebrow="HARDWARE_MODE=mock" title="Demo & Simulation" />
    <div className="grid gap-6 md:grid-cols-2">
      <div className="panel">
        <div className="eyebrow">Input Simulation</div>
        <h3 className="mt-2 text-lg font-semibold text-white">Student Events</h3>
        <label className="login-label mt-4">Target Student ID
          <input value={studentId} onChange={(e) => setStudentId(e.target.value)} placeholder="STU-..." />
        </label>
        <div className="mt-4 flex flex-col gap-2">
          <button onClick={() => simulate(`mock/rfid/${studentId || 'UNKNOWN'}`)} className="button-primary w-full justify-center">Simulate RFID Scan</button>
          <button onClick={() => simulate(`mock/face/${studentId || 'UNKNOWN'}`)} className="button-primary w-full justify-center">Simulate Face Recognition</button>
          <button onClick={() => simulate(`mock/guardian/${studentId || 'UNKNOWN'}?success=true`)} className="button-quiet w-full justify-center">Simulate Guardian Success</button>
          <button onClick={() => simulate(`mock/guardian/${studentId || 'UNKNOWN'}?success=false`)} className="button-quiet w-full justify-center text-rose-300">Simulate Guardian Failure</button>
        </div>
      </div>
    </div>
  </div>;
}
"""
    content += demo_component

with open("dashboard/client/src/App.tsx", "w") as f:
    f.write(content)
