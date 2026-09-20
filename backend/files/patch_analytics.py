import sys

with open("dashboard/client/src/App.tsx", "r") as f:
    content = f.read()

# Add summary state
if "const [summary, setSummary] =" not in content:
    content = content.replace(
        "const [students, setStudents] = useState<any[]>([]);",
        "const [students, setStudents] = useState<any[]>([]);\n  const [summary, setSummary] = useState<any>({});"
    )

    # Fetch summary
    old_promise = 'Promise.allSettled([api<SystemStatus>("/api/system/status"), api<any>("/api/attendance/today"), api<any>("/api/students")])'
    new_promise = 'Promise.allSettled([api<SystemStatus>("/api/system/status"), api<any>("/api/attendance/today"), api<any>("/api/students"), api<any>("/api/dashboard/summary")])'
    content = content.replace(old_promise, new_promise)
    
    old_then = ']).then(([s, a, st]) => {'
    new_then = ']).then(([s, a, st, sum]) => {'
    content = content.replace(old_then, new_then)
    
    old_set = 'if (st.status === "fulfilled") setStudents(st.value.records || []);'
    new_set = 'if (st.status === "fulfilled") setStudents(st.value.records || []);\n      if (sum.status === "fulfilled") setSummary(sum.value);'
    content = content.replace(old_set, new_set)

    # Pass summary to Analytics
    content = content.replace(
        '<Route path="/analytics" component={() => <Analytics />} />',
        '<Route path="/analytics" component={() => <Analytics summary={summary} />} />'
    )
    
    # Update Analytics component
    old_analytics = 'function Analytics() { return <div className="mx-auto max-w-[1500px] animate-enter">'
    new_analytics = 'function Analytics({ summary }: { summary: any }) { return <div className="mx-auto max-w-[1500px] animate-enter">'
    content = content.replace(old_analytics, new_analytics)
    
    # Update readouts in Analytics
    content = content.replace(
        '<div className="readout"><span>Peak check-in time</span><b>—</b></div>',
        '<div className="readout"><span>Check-ins today</span><b>{summary?.checkins_today ?? "—"}</b></div>'
    )
    content = content.replace(
        '<div className="readout"><span>Attendance rate</span><b>—</b></div>',
        '<div className="readout"><span>Currently Present</span><b>{summary?.currently_present ?? "—"}</b></div>'
    )
    content = content.replace(
        '<div className="readout"><span>Avg. time inside</span><b>—</b></div>',
        '<div className="readout"><span>Total Students</span><b>{summary?.total_students ?? "—"}</b></div>'
    )
    content = content.replace(
        '<div className="readout"><span>Guardian verification</span><b>—</b></div>',
        '<div className="readout"><span>Failed Verifications</span><b>{summary?.failed_verifications ?? "—"}</b></div>'
    )
    
    # Remove synthetic values warning
    content = content.replace('No synthetic values are displayed.', 'Showing live backend data.')

with open("dashboard/client/src/App.tsx", "w") as f:
    f.write(content)
