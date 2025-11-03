/**
 * Zendure Quick Control Card
 * Schneller Zugriff auf wichtigste Steuerelemente
 */

class ZendureQuickControlCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Operation mode entity is required');
    }
    this.config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.updateControls();
  }

  updateControls() {
    if (!this._hass || !this.config) return;

    const currentMode = this.getState(this.config.entity);
    const gridPower = this.config.entities?.grid_power ? 
      this.getStateValue(this.config.entities.grid_power) : 800;
    const targetSoc = this.config.entities?.target_soc ? 
      this.getStateValue(this.config.entities.target_soc) : 90;
    
    // Update Mode Buttons
    const modes = ['smart', 'smart_charging', 'grid_charging', 'off'];
    modes.forEach(mode => {
      const btn = this.shadowRoot.querySelector(`button[data-mode="${mode}"]`);
      if (btn) {
        btn.classList.toggle('active', currentMode === mode);
      }
    });

    // Update Values
    const gridInput = this.shadowRoot.querySelector('#grid-power-input');
    if (gridInput && gridInput.value !== gridPower.toString()) {
      gridInput.value = gridPower;
    }

    const socInput = this.shadowRoot.querySelector('#target-soc-input');
    if (socInput && socInput.value !== targetSoc.toString()) {
      socInput.value = targetSoc;
    }

    // Update Calibration Status
    if (this.config.show_calibration_status) {
      const calibStatus = this.getState(this.config.entities?.calibration_status);
      const nextCalib = this.getState(this.config.entities?.next_calibration);
      
      const statusEl = this.shadowRoot.querySelector('.calib-status');
      if (statusEl && calibStatus) {
        statusEl.textContent = calibStatus;
      }
      
      const nextEl = this.shadowRoot.querySelector('.calib-next');
      if (nextEl && nextCalib) {
        const date = new Date(nextCalib);
        nextEl.textContent = date.toLocaleDateString('de-DE');
      }
    }
  }

  getState(entityId) {
    if (!entityId || !this._hass) return null;
    const state = this._hass.states[entityId];
    return state ? state.state : null;
  }

  getStateValue(entityId) {
    if (!entityId || !this._hass) return 0;
    const state = this._hass.states[entityId];
    return state ? parseFloat(state.state) || 0 : 0;
  }

  setMode(mode) {
    if (!this._hass || !this.config.entity) return;

    this._hass.callService('select', 'select_option', {
      entity_id: this.config.entity,
      option: mode
    });
  }

  setGridPower(value) {
    if (!this._hass || !this.config.entities?.grid_power) return;

    this._hass.callService('number', 'set_value', {
      entity_id: this.config.entities.grid_power,
      value: parseFloat(value)
    });
  }

  setTargetSoc(value) {
    if (!this._hass || !this.config.entities?.target_soc) return;

    this._hass.callService('number', 'set_value', {
      entity_id: this.config.entities.target_soc,
      value: parseFloat(value)
    });
  }

  calibrateAll() {
    if (!this._hass || !this.config.entities?.calibrate) return;

    this._hass.callService('button', 'press', {
      entity_id: this.config.entities.calibrate
    });
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          padding: 16px;
        }
        .modes-container {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 8px;
          margin-bottom: 16px;
        }
        .mode-btn {
          padding: 12px 8px;
          border: 2px solid var(--divider-color);
          border-radius: 8px;
          background: var(--card-background-color);
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 12px;
          text-align: center;
        }
        .mode-btn:hover {
          background: var(--secondary-background-color);
        }
        .mode-btn.active {
          border-color: var(--primary-color);
          background: var(--primary-color);
          color: white;
          font-weight: bold;
        }
        .mode-btn .icon {
          font-size: 20px;
          margin-bottom: 4px;
        }
        .settings-container {
          display: flex;
          flex-direction: column;
          gap: 12px;
          margin-bottom: 16px;
        }
        .setting-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .setting-label {
          font-size: 14px;
          color: var(--secondary-text-color);
        }
        .setting-input {
          width: 100px;
          padding: 6px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
        }
        .calibrate-btn {
          width: 100%;
          padding: 12px;
          border: 2px solid var(--primary-color);
          border-radius: 8px;
          background: var(--primary-color);
          color: white;
          cursor: pointer;
          font-size: 14px;
          font-weight: bold;
          transition: all 0.2s ease;
        }
        .calibrate-btn:hover {
          opacity: 0.9;
          transform: scale(1.02);
        }
        .calib-info {
          margin-top: 12px;
          padding: 8px;
          background: var(--secondary-background-color);
          border-radius: 4px;
          font-size: 12px;
          text-align: center;
        }
      </style>
      <ha-card header="Zendure Steuerung">
        <div class="card-content">
          <!-- Operation Modes -->
          <div class="modes-container">
            <button class="mode-btn" data-mode="smart" onclick="this.getRootNode().host.setMode('smart')">
              <div class="icon">🎯</div>
              <div>Smart</div>
            </button>
            <button class="mode-btn" data-mode="smart_charging" onclick="this.getRootNode().host.setMode('smart_charging')">
              <div class="icon">⬆️</div>
              <div>Nur Laden</div>
            </button>
            <button class="mode-btn" data-mode="grid_charging" onclick="this.getRootNode().host.setMode('grid_charging')">
              <div class="icon">⚡</div>
              <div>Netzladen</div>
            </button>
            <button class="mode-btn" data-mode="off" onclick="this.getRootNode().host.setMode('off')">
              <div class="icon">⭕</div>
              <div>Aus</div>
            </button>
          </div>

          <!-- Settings -->
          <div class="settings-container">
            <div class="setting-row">
              <span class="setting-label">Netzladen Leistung:</span>
              <input type="number" id="grid-power-input" class="setting-input" 
                     min="100" max="3000" step="100"
                     onchange="this.getRootNode().host.setGridPower(this.value)" />
              <span style="font-size: 12px; margin-left: 4px;">W</span>
            </div>
            <div class="setting-row">
              <span class="setting-label">Ziel-SoC:</span>
              <input type="number" id="target-soc-input" class="setting-input" 
                     min="50" max="100" step="5"
                     onchange="this.getRootNode().host.setTargetSoc(this.value)" />
              <span style="font-size: 12px; margin-left: 4px;">%</span>
            </div>
          </div>

          <!-- Calibration -->
          ${this.config.show_calibration_status !== false ? `
          <button class="calibrate-btn" onclick="this.getRootNode().host.calibrateAll()">
            🔧 Alle kalibrieren
          </button>
          <div class="calib-info">
            <div>Status: <span class="calib-status">—</span></div>
            <div>Nächste: <span class="calib-next">—</span></div>
          </div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 5;
  }
}

customElements.define('zendure-quick-control-card', ZendureQuickControlCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'zendure-quick-control-card',
  name: 'Zendure Quick Control Card',
  description: 'Schnellzugriff auf Zendure Operation Modi und Einstellungen'
});

