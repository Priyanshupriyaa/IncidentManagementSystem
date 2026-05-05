/**
 * App.js — UPDATED
 *
 * What changed vs previous version:
 *   - fetchSignals URL changed from:
 *       /incidents/${compId}/signals
 *     to:
 *       /incidents/signals/${compId}
 *   This matches the fixed backend route GET /signals/{component_id}
 *   which avoids the FastAPI routing conflict with GET /{incident_id}.
 *   Everything else is identical to the previous version.
 */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './App.css';

const API = 'http://localhost:8000/api/v1';

const SEVERITY_ORDER = { P0: 0, P1: 1, P2: 2 };

function App() {
  const [incidents, setIncidents]             = useState([]);
  const [selectedSignals, setSelectedSignals] = useState(null);
  const [showRcaForm, setShowRcaForm]         = useState(false);
  const [activeIncident, setActiveIncident]   = useState(null);
  const [rcaData, setRcaData] = useState({
    root_cause: '',
    category: 'Infrastructure',
    fix_applied: '',
    prevention_steps: '',
    start_time: '',
    end_time: new Date().toISOString().slice(0, 16),
  });

  const fetchIncidents = async () => {
    try {
      const res = await axios.get(`${API}/incidents/`);
      const sorted = [...res.data].sort(
        (a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9)
      );
      setIncidents(sorted);
    } catch {
      console.error('Backend unreachable');
    }
  };

  const fetchSignals = async (compId) => {
    try {
      // FIXED: was /incidents/${compId}/signals — now /incidents/signals/${compId}
      const res = await axios.get(`${API}/incidents/signals/${compId}`);
      setSelectedSignals({ compId, signals: res.data });
    } catch {
      alert('Could not fetch audit logs');
    }
  };

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 5000);
    return () => clearInterval(interval);
  }, []);

  const transition = async (incident, nextState) => {
    try {
      await axios.put(`${API}/incidents/${incident.id}/status?next_state=${nextState}`);
      fetchIncidents();
    } catch (err) {
      alert(err.response?.data?.detail || 'Transition failed');
    }
  };

  const initiateClose = (incident) => {
    setActiveIncident(incident);
    setRcaData(prev => ({
      ...prev,
      start_time: incident.start_time ? incident.start_time.slice(0, 16) : '',
      end_time: new Date().toISOString().slice(0, 16),
    }));
    setShowRcaForm(true);
  };

  const handleRcaSubmit = async () => {
    if (!rcaData.root_cause || !rcaData.fix_applied) {
      alert('Root cause and fix applied are mandatory.');
      return;
    }
    try {
      await axios.put(
        `${API}/incidents/${activeIncident.id}/status?next_state=CLOSED`,
        rcaData
      );
      setShowRcaForm(false);
      fetchIncidents();
    } catch (err) {
      alert(err.response?.data?.detail || 'RCA submission failed');
    }
  };

  const statusColor = {
    OPEN: '#ef4444',
    INVESTIGATING: '#f59e0b',
    RESOLVED: '#3b82f6',
    CLOSED: '#22c55e',
  };

  return (
    <div className="App">
      <nav className="navbar">
        <h2>IMS Dashboard</h2>
        <div className="status">● System Live</div>
      </nav>

      <div className="container">
        {incidents.length === 0 ? (
          <p className="empty">No incidents. System is healthy!</p>
        ) : (
          <div className="grid">
            {incidents.map(inc => (
              <div
                key={inc.id}
                className={`card ${inc.severity}`}
                onClick={() => fetchSignals(inc.component_id)}
              >
                <div className="badge">{inc.severity}</div>
                <h3>{inc.component_id}</h3>
                <p>
                  Status:{' '}
                  <strong style={{ color: statusColor[inc.status] }}>
                    {inc.status}
                  </strong>
                </p>
                {inc.mttr_minutes && (
                  <p style={{ fontSize: 12, color: '#94a3b8' }}>
                    MTTR: {inc.mttr_minutes} min
                  </p>
                )}

                <div onClick={e => e.stopPropagation()}>
                  {inc.status === 'OPEN' && (
                    <button
                      className="close-btn"
                      style={{ background: '#f59e0b' }}
                      onClick={() => transition(inc, 'INVESTIGATING')}
                    >
                      Start Investigation
                    </button>
                  )}
                  {inc.status === 'INVESTIGATING' && (
                    <button
                      className="close-btn"
                      style={{ background: '#3b82f6' }}
                      onClick={() => transition(inc, 'RESOLVED')}
                    >
                      Mark Resolved
                    </button>
                  )}
                  {inc.status === 'RESOLVED' && (
                    <button
                      className="close-btn"
                      onClick={() => initiateClose(inc)}
                    >
                      Close + Submit RCA
                    </button>
                  )}
                  {inc.status === 'CLOSED' && (
                    <span style={{ fontSize: 12, color: '#22c55e' }}>✓ Closed</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* RCA Modal */}
      {showRcaForm && (
        <div className="modal-overlay">
          <div className="modal-content rca-modal">
            <h3>Root Cause Analysis — {activeIncident?.component_id}</h3>

            <div className="form-group">
              <label>Category</label>
              <select
                value={rcaData.category}
                onChange={e => setRcaData({ ...rcaData, category: e.target.value })}
              >
                <option>Infrastructure</option>
                <option>Code Bug</option>
                <option>Network</option>
                <option>Distributed Cache</option>
                <option>Async Queue</option>
                <option>Third-party Dependency</option>
              </select>
            </div>

            <div className="form-group">
              <label>Root Cause *</label>
              <textarea
                value={rcaData.root_cause}
                onChange={e => setRcaData({ ...rcaData, root_cause: e.target.value })}
                placeholder="What was the actual root cause?"
                rows={3}
              />
            </div>

            <div className="form-group">
              <label>Fix Applied *</label>
              <textarea
                value={rcaData.fix_applied}
                onChange={e => setRcaData({ ...rcaData, fix_applied: e.target.value })}
                placeholder="What was done to resolve the incident?"
                rows={3}
              />
            </div>

            <div className="form-group">
              <label>Prevention Steps</label>
              <textarea
                value={rcaData.prevention_steps}
                onChange={e => setRcaData({ ...rcaData, prevention_steps: e.target.value })}
                placeholder="How do we prevent recurrence?"
                rows={3}
              />
            </div>

            <div className="time-section">
              <div className="form-group">
                <label>Incident Start</label>
                <input
                  type="datetime-local"
                  value={rcaData.start_time}
                  onChange={e => setRcaData({ ...rcaData, start_time: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>Incident End</label>
                <input
                  type="datetime-local"
                  value={rcaData.end_time}
                  onChange={e => setRcaData({ ...rcaData, end_time: e.target.value })}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button className="submit-rca-btn" onClick={handleRcaSubmit}>
                Submit & Close Incident
              </button>
              <button className="cancel-btn" onClick={() => setShowRcaForm(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Raw Signals Modal */}
      {selectedSignals && (
        <div className="modal-overlay" onClick={() => setSelectedSignals(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Audit Log: {selectedSignals.compId}</h3>
              <button className="close-x" onClick={() => setSelectedSignals(null)}>×</button>
            </div>
            <div className="signal-list">
              {selectedSignals.signals.length === 0 ? (
                <p>No raw signals found in MongoDB.</p>
              ) : (
                selectedSignals.signals.map((s, i) => (
                  <div key={i} className="signal-item">
                    <pre>{JSON.stringify(s, null, 2)}</pre>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;