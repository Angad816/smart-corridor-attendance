import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const navItems = [
  ['dashboard', 'Dashboard', 'D'],
  ['register', 'Register student', '+'],
  ['recognition', 'Live recognition', 'O'],
  ['attendance', "Today's attendance", 'A'],
  ['reports', 'Attendance report', 'R'],
  ['unknown', 'Unknown events', '!'],
]

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || 'Could not complete the request.')
  return data
}

const today = () => new Date().toISOString().slice(0, 10)
const niceDate = (date) => new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

function Status({ value }) {
  return <span className={`status-pill ${value.toLowerCase().replaceAll(' ', '-')}`}>{value}</span>
}

function Header({ eyebrow, title, children }) {
  return <header className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div>{children}</header>
}

function useWebcam(active) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!active) return undefined
    let cancelled = false
    navigator.mediaDevices.getUserMedia({ video: true, audio: false }).then((stream) => {
      if (cancelled) return stream.getTracks().forEach((track) => track.stop())
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
    }).catch(() => setError('Allow webcam permission, then try again.'))
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [active])

  const frame = useCallback(() => {
    const video = videoRef.current
    if (!video?.videoWidth) throw new Error('Camera is starting. Please wait a moment.')
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    return canvas.toDataURL('image/jpeg', 0.88)
  }, [])

  return { videoRef, error, frame }
}

function Camera({ active, videoRef, label }) {
  return <div className={`camera-feed ${active ? 'running' : ''}`}>
    <video className="webcam-video" ref={videoRef} autoPlay muted playsInline />
    <div className="scan-line" />
    <div className="camera-copy"><span className="live-dot" /> {active ? label : 'Camera is paused'}</div>
    <div className="face-box"><span>{active ? 'Camera ready' : 'Camera paused'}</span></div>
  </div>
}

function AttendanceTable({ rows }) {
  return <div className="table-wrap">
    <table>
      <thead><tr><th>Student</th><th>Roll no.</th><th>Class</th><th>Entry time</th><th>Status</th><th>Delay</th></tr></thead>
      <tbody>{rows.length ? rows.map((row) => <tr key={`${row.roll_number}-${row.attendance_date}`}>
        <td><strong>{row.name}</strong></td>
        <td>{row.roll_number}</td>
        <td>{row.class_division}</td>
        <td>{row.entry_time}</td>
        <td><Status value={row.status} /></td>
        <td>{row.status === 'Late' ? `${row.late_minutes || 0} min` : '-'}</td>
      </tr>) : <tr><td colSpan="6" className="empty-row">No attendance records found.</td></tr>}</tbody>
    </table>
  </div>
}

function exportRowsToCsv(rows, filename) {
  const headers = ['Name', 'Roll Number', 'Class', 'Date', 'Entry Time', 'Status', 'Late Minutes']
  const csvRows = rows.map((row) => [row.name, row.roll_number, row.class_division, row.attendance_date, row.entry_time, row.status, row.late_minutes || 0])
  const csv = [headers, ...csvRows].map((cells) => cells.map((cell) => `"${String(cell ?? '').replaceAll('"', '""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

function Dashboard({ go }) {
  const [summary, setSummary] = useState(null)
  const [attendance, setAttendance] = useState([])

  useEffect(() => {
    Promise.all([request('/api/dashboard-summary'), request('/api/attendance')]).then(([a, b]) => {
      setSummary(a)
      setAttendance(b)
    }).catch(() => {})
  }, [])

  const cards = summary ? [
    ['Registered students', summary.registered_students, ''],
    ['Present today', summary.present_today, 'green'],
    ['Late today', summary.late_today, 'amber'],
    ['Manual review', summary.unknown_events_today, 'red'],
  ] : []

  return <>
    <Header eyebrow="Overview" title="Good morning, Admin"><button className="primary-button" onClick={() => go('recognition')}>Start live recognition <span>-&gt;</span></button></Header>
    <section className="stat-grid">{cards.map(([label, count, color]) => <article className={`metric-card ${color}`} key={label}><span>{label}</span><strong>{count}</strong><small>{label === 'Late today' ? `School time: ${summary.school_start_time}` : 'Live database count'}</small></article>)}</section>
    <section className="dashboard-grid">
      <article className="panel attendance-panel"><div className="panel-title"><div><h2>Today's attendance</h2><p>{niceDate(today())}</p></div><button className="text-button" onClick={() => go('attendance')}>View all</button></div><AttendanceTable rows={attendance.slice(0, 5)} /></article>
      <article className="corridor-card"><div className="grid-lines" /><p className="eyebrow">Camera status</p><div className="online-label"><span /> One entrance camera ready</div><h2>Corridor monitoring<br />is ready.</h2><p>Attendance is marked only after a safe face match.</p><button className="secondary-on-dark" onClick={() => go('recognition')}>Open live camera</button></article>
    </section>
  </>
}

function Register() {
  const [cameraOn, setCameraOn] = useState(false)
  const [photo, setPhoto] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [students, setStudents] = useState([])
  const { videoRef, error: cameraError, frame } = useWebcam(cameraOn)

  const loadStudents = useCallback(() => request('/api/students').then(setStudents).catch(() => setStudents([])), [])
  useEffect(() => { loadStudents() }, [loadStudents])

  const capture = () => {
    try {
      setPhoto(frame())
      setMessage('Face image captured.')
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }

  async function submit(event) {
    event.preventDefault()
    if (!photo) return setError('Capture one clear face before registering.')
    const form = new FormData(event.currentTarget)
    setSaving(true)
    setError('')
    try {
      const student = await request('/api/students', { method: 'POST', body: JSON.stringify({ name: form.get('name'), roll_number: form.get('roll_number'), class_division: form.get('class_division'), image_data: photo }) })
      setMessage(`${student.name} was registered successfully.`)
      setPhoto('')
      event.currentTarget.reset()
      loadStudents()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return <>
    <Header eyebrow="Student directory" title="Register a student" />
    <section className="register-layout">
      <form className="panel form-panel" onSubmit={submit}><h2>Student details</h2><p>Enter details and capture one clear face from the laptop camera.</p><label>Full name<input name="name" required placeholder="e.g. Asha Shah" /></label><label>Roll number<input name="roll_number" required placeholder="e.g. 101" /></label><label>Class / division<input name="class_division" required placeholder="e.g. 10-A" /></label><button className="primary-button" disabled={saving}>{saving ? 'Registering...' : 'Register student'}</button>{message && <div className="success-message">{message}</div>}{error && <div className="error-message">{error}</div>}</form>
      <article className="panel capture-panel">{cameraOn ? <Camera active videoRef={videoRef} label="Registration camera" /> : <div className="camera-placeholder"><div className="face-guide"><span /><span /><span /><span /></div><p>Camera preview</p></div>}<h2>Face capture</h2><p>Use good lighting and keep only one person in the frame.</p><div className="button-row">{cameraOn ? <button className="outline-button" onClick={capture}>Capture face</button> : <button className="outline-button" onClick={() => setCameraOn(true)}>Start camera</button>}{photo && <span className="capture-status">Face captured</span>}</div>{cameraError && <div className="error-message">{cameraError}</div>}</article>
    </section>
    <section className="panel report-panel student-list-panel"><div className="panel-title"><div><h2>Registered students</h2><p>{students.length} student{students.length === 1 ? '' : 's'} saved locally</p></div></div><div className="table-wrap"><table><thead><tr><th>Name</th><th>Roll no.</th><th>Class</th><th>Registered</th></tr></thead><tbody>{students.length ? students.map((student) => <tr key={student.id}><td><strong>{student.name}</strong></td><td>{student.roll_number}</td><td>{student.class_division}</td><td>{new Date(student.created_at).toLocaleDateString()}</td></tr>) : <tr><td colSpan="4" className="empty-row">No students registered yet.</td></tr>}</tbody></table></div></section>
  </>
}

function Recognition() {
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const { videoRef, error: cameraError, frame } = useWebcam(running)
  const working = useRef(false)

  const scan = useCallback(async () => {
    if (working.current) return
    try {
      working.current = true
      const image_data = frame()
      const data = await request('/api/recognition/identify', { method: 'POST', body: JSON.stringify({ image_data }) })
      setResult(data)
      setError('')
    } catch (e) {
      if (!e.message.includes('starting')) setError(e.message)
    } finally {
      working.current = false
    }
  }, [frame])

  useEffect(() => {
    if (!running) return undefined
    const initial = setTimeout(scan, 1200)
    const repeat = setInterval(scan, 4000)
    return () => {
      clearTimeout(initial)
      clearInterval(repeat)
    }
  }, [running, scan])

  const recognized = result?.recognized

  return <>
    <Header eyebrow="One entrance camera" title="Live recognition"><button className={running ? 'outline-button' : 'primary-button'} onClick={() => { setRunning(!running); setResult(null); setError('') }}>{running ? 'Stop camera' : 'Start camera'}</button></Header>
    <section className="live-layout">
      <Camera active={running} videoRef={videoRef} label="Live camera feed" />
      <article className="recognition-card"><p className="eyebrow">Recognition result</p><Status value={!running ? 'Waiting' : !result ? 'Scanning' : recognized ? 'Recognized' : 'Unknown'} /><h2>{!running ? 'Start the camera' : !result ? 'Looking for a face...' : recognized ? result.name : 'Unknown / Manual Review'}</h2><p>{recognized ? `Roll no. ${result.roll_number} | Class ${result.class_division}` : result?.reason || 'The latest recognition result will appear here.'}</p>{recognized && <div className="result-details"><div><span>Entry time</span><strong>{result.entry_time}</strong></div><div><span>Attendance</span><strong>{result.attendance_status}</strong></div><div><span>Late minutes</span><strong>{result.late_minutes || 0} min</strong></div><div><span>Match result</span><strong>Safe match</strong></div></div>}<p className="notice">Unknown or low-confidence matches never mark attendance. {recognized && !result.marked_now ? 'This student was already marked today.' : ''}</p>{(error || cameraError) && <div className="error-message">{error || cameraError}</div>}</article>
    </section>
  </>
}

function Attendance() {
  const [date, setDate] = useState(today())
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState([])
  useEffect(() => { request(`/api/attendance?date=${date}&query=${encodeURIComponent(query)}`).then(setRows).catch(() => setRows([])) }, [date, query])
  return <><Header eyebrow="Daily record" title="Today's attendance" /><section className="panel report-panel"><div className="filter-row"><label>Search students<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name, roll number, or class" /></label><label>Date<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label><button className="outline-button export-button" disabled={!rows.length} onClick={() => exportRowsToCsv(rows, `attendance-${date}.csv`)}>Export CSV</button></div><AttendanceTable rows={rows} /></section></>
}

function Reports() {
  const [date, setDate] = useState(today())
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState([])
  function search(event) {
    event.preventDefault()
    request(`/api/attendance?date=${date}&query=${encodeURIComponent(query)}`).then(setRows).catch(() => setRows([]))
  }
  return <><Header eyebrow="Historical data" title="Attendance report" /><section className="panel report-panel"><form className="filter-row report-form" onSubmit={search}><label>Student / class<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name, roll number, or class" /></label><label>Date<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label><button className="primary-button">Search report</button><button type="button" className="outline-button export-button" disabled={!rows.length} onClick={() => exportRowsToCsv(rows, `attendance-report-${date}.csv`)}>Export CSV</button></form><AttendanceTable rows={rows} /></section></>
}

function Unknown() {
  const [events, setEvents] = useState([])
  useEffect(() => { request('/api/unknown-events').then(setEvents).catch(() => {}) }, [])
  return <><Header eyebrow="Review queue" title="Unknown events" /><section className="panel report-panel"><div className="review-note"><strong>Manual review required</strong><span>These events never receive attendance automatically.</span></div><div className="table-wrap"><table><thead><tr><th>Event time</th><th>Reason</th><th>Snapshot</th></tr></thead><tbody>{events.length ? events.map((event) => <tr key={event.id}><td>{new Date(event.event_time).toLocaleString()}</td><td>{event.reason}</td><td>{event.snapshot_path ? <a className="snapshot-link" href={`${API}/snapshots/${event.snapshot_path}`} target="_blank" rel="noreferrer">View image</a> : <span className="snapshot">No image saved</span>}</td></tr>) : <tr><td className="empty-row" colSpan="3">No unknown events have been recorded.</td></tr>}</tbody></table></div></section></>
}

export default function App() {
  const [page, go] = useState('dashboard')
  const views = { dashboard: <Dashboard go={go} />, register: <Register />, recognition: <Recognition />, attendance: <Attendance />, reports: <Reports />, unknown: <Unknown /> }

  return <div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => go('dashboard')}><span className="brand-mark">S</span><span>Smart<br /><b>Corridor</b></span></button>
      <nav>{navItems.map(([id, label, icon]) => <button className={page === id ? 'nav-item active' : 'nav-item'} key={id} onClick={() => go(id)}><span>{icon}</span>{label}</button>)}</nav>
      <div className="sidebar-footer"><span className="online-dot" /> System online<br /><small>Local laptop mode</small></div>
    </aside>
    <main><div className="topbar"><span>Face Recognition Attendance System</span><div className="admin-avatar">AD</div></div><div className="content">{views[page]}</div></main>
  </div>
}
