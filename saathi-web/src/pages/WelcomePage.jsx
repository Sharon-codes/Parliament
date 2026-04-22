import { SUPPORTED_LANGUAGES } from "../lib/config";

export default function WelcomePage({
  profile,
  saving,
  workspaceLoading,
  workspaceStatus,
  form,
  setForm,
  onSave,
  onConnectWorkspace,
}) {
  const isWorkspaceConnected = workspaceStatus?.connected;
  
  return (
    <div className="welcome-shell">
      <section className="welcome-card">
        <div className="brand-pill">Onboarding</div>
        <h1>Personalize Saathi</h1>
        
        <form
          className="welcome-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (isWorkspaceConnected) {
              onSave();
            }
          }}
        >
          <div className="onboarding-step">
            <h3>1. Professional Basics</h3>
            <div className="field-group">
              <label className="field">
                <span>Full Name</span>
                <input
                  value={form.full_name}
                  onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))}
                  placeholder="e.g. Sharon"
                />
              </label>

              <label className="field">
                <span>Saathi's Language</span>
                <select
                  value={form.language}
                  onChange={(event) => setForm((current) => ({ ...current, language: event.target.value }))}
                >
                  {SUPPORTED_LANGUAGES.map((language) => (
                    <option key={language} value={language}>
                      {language}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className="workspace-card onboarding-step">
            <div className="step-header">
              <h3>2. Workspace Integration</h3>
              <p>Saathi needs Google to manage your day effectively.</p>
            </div>
            
            <div className="workspace-status-area">
              <button
                type="button"
                className={`secondary-button ${isWorkspaceConnected ? "success-border" : ""}`}
                onClick={onConnectWorkspace}
                disabled={workspaceLoading}
              >
                {workspaceLoading ? "Opening Google..." : isWorkspaceConnected ? "✓ Connected to Google" : "Connect Gmail & Calendar"}
              </button>
              
              {!isWorkspaceConnected && (
                <span className="required-tag">Mandatory to continue</span>
              )}
            </div>
          </div>

          <div className="welcome-actions">
            <button type="submit" className="primary-button large-btn" disabled={saving || !isWorkspaceConnected}>
              {saving ? "Finalizing..." : "Go to Dashboard"}
            </button>
          </div>
        </form>

        <div className="auth-note">
          <p>
            Signed in as <strong>{profile?.email || "your Google account"}</strong>. You can
            update language and voice later in Settings.
          </p>
        </div>
      </section>
    </div>
  );
}
