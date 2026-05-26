import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

const API = "http://127.0.0.1:8000";

export default function App() {
  const [tab, setTab] = useState("deploy");
  const [functions, setFunctions] = useState([]);
  const [name, setName] = useState("");
  const [runtime, setRuntime] = useState("python");
  const [file, setFile] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [output, setOutput] = useState("");
  const [outputImage, setOutputImage] = useState(null);
  const [loadingId, setLoadingId] = useState(null);

  const fetchFunctions = async () => {
    const res = await axios.get(`${API}/functions`);
    setFunctions(res.data);
  };

  useEffect(() => {
    fetchFunctions();
  }, []);

  const handleDeploy = async () => {
    if (!file || !name) return alert("Fill in name and select a file.");
    const form = new FormData();
    form.append("name", name);
    form.append("runtime", runtime);
    form.append("file", file);
    if (imageFile) form.append("image", imageFile);
    const res = await axios.post(`${API}/functions/upload`, form);
    const deps = res.data.detected_deps || [];
    if (deps.length > 0) {
      alert(`Function deployed!\n\nDetected dependencies:\n${deps.map(d => `• ${d}`).join("\n")}\n\nThey will be auto-installed when you run it.`);
    } else {
      alert("Function deployed! No external dependencies detected.");
    }
    fetchFunctions();
    setTab("functions");
  };

  const handleInvoke = async (id) => {
    setLoadingId(id);
    setOutputImage(null);
    try {
      const res = await axios.post(`${API}/functions/${id}/invoke`, {});
      const data = res.data;

      // Check if stdout contains a base64 image marker
      if (data.stdout && data.stdout.includes("IMAGE_OUTPUT_BASE64:")) {
        const lines = data.stdout.split("\n");
        const imgLine = lines.find(l => l.startsWith("IMAGE_OUTPUT_BASE64:"));
        const b64 = imgLine.replace("IMAGE_OUTPUT_BASE64:", "").trim();
        setOutputImage(b64);
        // Show the rest of the text output without the base64 line
        const textOnly = lines.filter(l => !l.startsWith("IMAGE_OUTPUT_BASE64:")).join("\n");
        setOutput(JSON.stringify({ ...data, stdout: textOnly }, null, 2));
      } else {
        setOutput(JSON.stringify(data, null, 2));
      }
      setTab("output");
    } finally {
      setLoadingId(null);
    }
  };

  const handleDelete = async (id) => {
    await axios.delete(`${API}/functions/${id}`);
    fetchFunctions();
  };

  return (
    <div className="app">
      <h1 className="title">⚡ FaaS Runner</h1>

      <div className="tabs">
        {["deploy", "functions", "output"].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`tab-btn ${tab === t ? "active" : ""}`}
          >
            {t.toUpperCase()}
          </button>
        ))}
      </div>

      {tab === "deploy" && (
        <div className="form">
          <input
            placeholder="Function name"
            value={name}
            onChange={e => setName(e.target.value)}
            className="input"
          />
          <select
            value={runtime}
            onChange={e => setRuntime(e.target.value)}
            className="input"
          >
            <option value="python">Python</option>
            <option value="node">Node.js</option>
            <option value="bash">Bash</option>
          </select>
          <input
            type="file"
            onChange={e => setFile(e.target.files[0])}
            className="input file-input"
          />
          <label className="input-label">Input Image (optional)</label>
          <input
            type="file"
            accept="image/*"
            onChange={e => setImageFile(e.target.files[0])}
            className="input file-input"
          />
          <button onClick={handleDeploy} className="deploy-btn">
            🚀 Deploy
          </button>
        </div>
      )}

      {tab === "functions" && (
        <div className="function-list">
          {functions.length === 0 && (
            <p className="empty">No functions deployed yet.</p>
          )}
          {functions.map(fn => (
            <div key={fn.id} className="function-card">
              <div className="fn-info">
                <span className="fn-name">{fn.name}</span>
                <span className="fn-runtime">({fn.runtime})</span>
                <p className="fn-meta">ID: {fn.id} · {fn.filename}</p>
                {fn.deps && fn.deps.length > 0 && (
                  <p className="fn-deps">📦 {fn.deps.join(", ")}</p>
                )}
              </div>
              <div className="fn-actions">
                <button
                  onClick={() => handleInvoke(fn.id)}
                  className={`run-btn ${loadingId === fn.id ? "loading" : ""}`}
                  disabled={loadingId === fn.id}
                >
                  {loadingId === fn.id ? (
                    <span className="spinner-wrap">
                      <span className="spinner" /> Running...
                    </span>
                  ) : "▶ Run"}
                </button>
                <button
                  onClick={() => handleDelete(fn.id)}
                  className="delete-btn"
                  disabled={loadingId === fn.id}
                >
                  🗑 Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "output" && (
        <div>
          {outputImage && (
            <div className="image-output">
              <p className="image-label">Grayscale Output:</p>
              <img
                src={`data:image/png;base64,${outputImage}`}
                alt="Output"
                className="output-image"
              />
            </div>
          )}
          <pre className="output-box">
            {output || "No output yet. Run a function first."}
          </pre>
        </div>
      )}
    </div>
  );
}