/**
 * Zendure Power Flow Card
 * Visualisiert den Energie-Fluss: Solar → Batterie → Haus → Netz
 */

class ZendurePowerFlowCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Entity is required');
    }
    this.config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.updateValues();
  }

  updateValues() {
    if (!this._hass || !this.config) return;

    // Hole Werte von Entities
    const solar = this.getStateValue(this.config.entities?.solar) || 0;
    const batteryKwh = this.getStateValue(this.config.entities?.battery) || 0;
    const batterySoc = this.getStateValue(this.config.entities?.battery_soc) || 0;
    const home = this.getStateValue(this.config.entities?.home) || 0;
    const grid = this.getStateValue(this.config.entities?.grid) || 0;
    const operation = this.getState(this.config.entities?.operation) || 'unknown';

    // Berechne Energie-Flüsse
    const flows = this.calculateFlows(solar, home, grid, operation);

    // Update UI
    this.updateUI(solar, batteryKwh, batterySoc, home, grid, operation, flows);
  }

  getStateValue(entityId) {
    if (!entityId || !this._hass) return 0;
    const state = this._hass.states[entityId];
    return state ? parseFloat(state.state) || 0 : 0;
  }

  getState(entityId) {
    if (!entityId || !this._hass) return null;
    const state = this._hass.states[entityId];
    return state ? state.state : null;
  }

  calculateFlows(solar, home, grid, operation) {
    // Bestimme Energie-Fluss Richtungen
    const flows = {
      solarToBattery: false,
      solarToHome: false,
      batteryToHome: false,
      gridToBattery: false,
      gridToHome: false,
      homeToGrid: false
    };

    switch(operation) {
      case 'grid_charging':
        flows.gridToBattery = true;
        break;
      case 'smart':
      case 'smart_charging':
      case 'smart_discharging':
        if (solar > 0) {
          if (solar > home) {
            flows.solarToHome = true;
            flows.solarToBattery = true;
          } else {
            flows.solarToHome = true;
          }
        }
        if (grid < 0) {
          flows.solarToBattery = true;
        } else if (grid > 0) {
          if (operation !== 'smart_charging') {
            flows.batteryToHome = true;
          } else {
            flows.gridToHome = true;
          }
        }
        break;
    }

    return flows;
  }

  updateUI(solar, batteryKwh, batterySoc, home, grid, operation, flows) {
    const card = this.shadowRoot.querySelector('.card-content');
    if (!card) return;

    const solarClass = flows.solarToBattery || flows.solarToHome ? 'active producing' : '';
    const batteryClass = flows.batteryToHome ? 'active discharging' : flows.solarToBattery || flows.gridToBattery ? 'active charging' : '';
    const gridClass = grid < 0 ? 'exporting' : grid > 0 ? 'importing' : '';

    card.innerHTML = `
      <div class="flow-container">
        <!-- Solar -->
        <div class="node solar ${solarClass}">
          <div class="icon">☀️</div>
          <div class="label">Solar</div>
          <div class="value">${Math.abs(solar).toFixed(0)} W</div>
        </div>

        <!-- Batterie -->
        <div class="node battery ${batteryClass}">
          <div class="icon">🔋</div>
          <div class="label">Batterie</div>
          <div class="value">${batterySoc.toFixed(0)}%</div>
          <div class="sub-value">${batteryKwh.toFixed(1)} kWh</div>
        </div>

        <!-- Haus -->
        <div class="node home">
          <div class="icon">🏠</div>
          <div class="label">Haus</div>
          <div class="value">${home.toFixed(0)} W</div>
        </div>

        <!-- Netz -->
        <div class="node grid ${gridClass}">
          <div class="icon">⚡</div>
          <div class="label">Netz</div>
          <div class="value">${grid >= 0 ? '+' : ''}${grid.toFixed(0)} W</div>
        </div>

        <!-- Verbindungen (SVG) -->
        <svg class="connections" viewBox="0 0 400 300">
          <!-- Solar → Batterie -->
          <path class="flow-line ${flows.solarToBattery ? 'active' : ''}" 
                d="M 100 80 L 100 140" 
                marker-end="url(#arrowhead)"/>
          
          <!-- Solar → Haus -->
          <path class="flow-line ${flows.solarToHome ? 'active' : ''}" 
                d="M 120 60 L 280 140" 
                marker-end="url(#arrowhead)"/>
          
          <!-- Batterie → Haus -->
          <path class="flow-line ${flows.batteryToHome ? 'active' : ''}" 
                d="M 140 160 L 260 160" 
                marker-end="url(#arrowhead)"/>
          
          <!-- Netz → Batterie -->
          <path class="flow-line ${flows.gridToBattery ? 'active' : ''}" 
                d="M 100 220 L 100 180" 
                marker-end="url(#arrowhead)"/>
          
          <!-- Netz → Haus -->
          <path class="flow-line ${flows.gridToHome ? 'active' : ''}" 
                d="M 120 240 L 280 180" 
                marker-end="url(#arrowhead)"/>
          
          <!-- Haus → Netz -->
          <path class="flow-line ${flows.homeToGrid ? 'active' : ''}" 
                d="M 280 180 L 120 240" 
                marker-end="url(#arrowhead)"/>
          
          <!-- Arrow marker -->
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="5" refY="5" orient="auto">
              <polygon points="0 0, 10 5, 0 10" fill="currentColor" />
            </marker>
          </defs>
        </svg>

        <!-- Status -->
        <div class="status-bar">
          Mode: <strong>${this.translateMode(operation)}</strong>
        </div>
      </div>
    `;
  }

  translateMode(mode) {
    const translations = {
      'smart': 'Smart Matching',
      'smart_charging': 'Smart nur Laden',
      'smart_discharging': 'Smart nur Entladen',
      'grid_charging': 'Netzladen',
      'manual': 'Manuell',
      'off': 'Aus'
    };
    return translations[mode] || mode;
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          padding: 16px;
        }
        .flow-container {
          position: relative;
          height: 350px;
          font-family: var(--paper-font-body1_-_font-family);
        }
        .node {
          position: absolute;
          text-align: center;
          padding: 12px;
          border-radius: 8px;
          background: var(--card-background-color);
          border: 2px solid var(--divider-color);
          min-width: 100px;
          transition: all 0.3s ease;
        }
        .node.active {
          border-color: var(--primary-color);
          box-shadow: 0 0 10px var(--primary-color);
        }
        .node.charging {
          border-color: #4caf50;
        }
        .node.discharging {
          border-color: #ff9800;
        }
        .node.producing {
          border-color: #ffeb3b;
        }
        .node .icon {
          font-size: 32px;
          margin-bottom: 4px;
        }
        .node .label {
          font-size: 12px;
          color: var(--secondary-text-color);
        }
        .node .value {
          font-size: 18px;
          font-weight: bold;
          margin-top: 4px;
        }
        .node .sub-value {
          font-size: 14px;
          color: var(--secondary-text-color);
        }
        .solar { top: 20px; left: 50px; }
        .battery { top: 140px; left: 50px; }
        .home { top: 140px; right: 50px; }
        .grid { top: 240px; left: 50px; }
        
        .connections {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          pointer-events: none;
        }
        .flow-line {
          fill: none;
          stroke: var(--divider-color);
          stroke-width: 2;
          opacity: 0.3;
        }
        .flow-line.active {
          stroke: var(--primary-color);
          opacity: 1;
          animation: flow 2s linear infinite;
        }
        @keyframes flow {
          0% { stroke-dashoffset: 20; }
          100% { stroke-dashoffset: 0; }
        }
        .flow-line.active {
          stroke-dasharray: 5 5;
        }
        .grid.exporting {
          border-color: #4caf50;
        }
        .grid.importing {
          border-color: #f44336;
        }
        .status-bar {
          position: absolute;
          bottom: 10px;
          left: 50%;
          transform: translateX(-50%);
          font-size: 14px;
          color: var(--secondary-text-color);
        }
      </style>
      <ha-card header="Zendure Energie-Fluss">
        <div class="card-content"></div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 5;
  }
}

customElements.define('zendure-power-flow-card', ZendurePowerFlowCard);

// Tell Home Assistant about the card
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'zendure-power-flow-card',
  name: 'Zendure Power Flow Card',
  description: 'Visualisiert den Energie-Fluss zwischen Solar, Batterie, Haus und Netz'
});

