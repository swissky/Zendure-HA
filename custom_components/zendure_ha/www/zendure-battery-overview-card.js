/**
 * Zendure Battery Overview Card
 * Zeigt alle Zendure-Batterien mit SoC, Temperatur, Leistung
 */

class ZendureBatteryOverviewCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    if (!config.devices || config.devices.length === 0) {
      throw new Error('Devices are required');
    }
    this.config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.updateDevices();
  }

  updateDevices() {
    if (!this._hass || !this.config) return;

    const container = this.shadowRoot.querySelector('.devices-container');
    if (!container) return;

    container.innerHTML = '';

    // Hole Daten für jedes Gerät
    this.config.devices.forEach(device => {
      const deviceCard = this.createDeviceCard(device);
      container.appendChild(deviceCard);
    });

    // Gesamt-Statistik
    this.updateTotalStats();
  }

  createDeviceCard(deviceConfig) {
    const card = document.createElement('div');
    card.className = 'device-card';

    // Hole Entity-States
    const socState = this._hass.states[deviceConfig.entity];
    const soc = socState ? parseFloat(socState.state) || 0 : 0;
    
    // Versuche verwandte Entities zu finden
    const baseEntity = deviceConfig.entity.replace('_electric_level', '');
    const tempEntity = `${baseEntity}_max_temp`;
    const powerEntity = `${baseEntity}_pack_input_power`;
    const availableEntity = `${baseEntity}_available_kwh`;
    const onlineEntity = `${baseEntity}_connection_status`;

    const temp = this.getStateValue(tempEntity);
    const power = this.getStateValue(powerEntity);
    const available = this.getStateValue(availableEntity);
    const online = this.getStateValue(onlineEntity) > 5;

    // Berechne Balken-Breite
    const barWidth = Math.max(0, Math.min(100, soc));
    
    // Bestimme Farbe basierend auf SoC
    let barColor = '#4caf50'; // Grün
    if (soc < 20) barColor = '#f44336'; // Rot
    else if (soc < 50) barColor = '#ff9800'; // Orange
    
    // Bestimme Status
    const isCharging = power < 0;
    const isDischarging = power > 0;
    const statusIcon = online ? '🟢' : '🔴';
    const statusText = online ? 'Online' : 'Offline';

    card.innerHTML = `
      <div class="device-header">
        <span class="device-name">${deviceConfig.name || 'Gerät'}</span>
        <span class="device-status ${online ? 'online' : 'offline'}">${statusIcon} ${statusText}</span>
      </div>
      
      <div class="battery-bar-container">
        <div class="battery-bar" style="width: ${barWidth}%; background-color: ${barColor}"></div>
        <div class="battery-percentage">${soc.toFixed(0)}%</div>
      </div>
      
      <div class="device-stats">
        <div class="stat">
          <span class="stat-label">Energie:</span>
          <span class="stat-value">${available > 0 ? available.toFixed(1) : '—'} kWh</span>
        </div>
        ${temp > 0 ? `
        <div class="stat">
          <span class="stat-label">🌡️</span>
          <span class="stat-value ${temp > 40 ? 'warning' : ''}">${temp.toFixed(0)}°C</span>
        </div>` : ''}
        <div class="stat">
          <span class="stat-label">⚡</span>
          <span class="stat-value ${isCharging ? 'charging' : isDischarging ? 'discharging' : ''}">
            ${power !== 0 ? (power > 0 ? '+' : '') + power.toFixed(0) + ' W' : 'Standby'}
          </span>
        </div>
      </div>
    `;

    return card;
  }

  updateTotalStats() {
    const total = this.shadowRoot.querySelector('.total-stats');
    if (!total) return;

    let totalKwh = 0;
    let totalCapacity = 0;
    let onlineCount = 0;

    this.config.devices.forEach(device => {
      const baseEntity = device.entity.replace('_electric_level', '');
      const available = this.getStateValue(`${baseEntity}_available_kwh`);
      const online = this.getStateValue(`${baseEntity}_connection_status`) > 5;
      
      if (available > 0) {
        totalKwh += available;
        // Schätze Kapazität (vereinfacht)
        const soc = this.getStateValue(device.entity);
        if (soc > 0) {
          totalCapacity += available / (soc / 100);
        }
      }
      if (online) onlineCount++;
    });

    const totalSoc = totalCapacity > 0 ? (totalKwh / totalCapacity * 100) : 0;

    total.innerHTML = `
      <strong>Gesamt:</strong> 
      ${totalKwh.toFixed(1)} / ${totalCapacity.toFixed(1)} kWh 
      (${totalSoc.toFixed(0)}%)
      &nbsp;|&nbsp;
      ${onlineCount} / ${this.config.devices.length} Geräte online
    `;
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          padding: 16px;
        }
        .devices-container {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .device-card {
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 12px;
        }
        .device-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }
        .device-name {
          font-weight: bold;
          font-size: 14px;
        }
        .device-status {
          font-size: 12px;
        }
        .device-status.online {
          color: #4caf50;
        }
        .device-status.offline {
          color: #f44336;
        }
        .battery-bar-container {
          position: relative;
          height: 24px;
          background: var(--divider-color);
          border-radius: 4px;
          overflow: hidden;
          margin-bottom: 8px;
        }
        .battery-bar {
          height: 100%;
          transition: width 0.3s ease, background-color 0.3s ease;
        }
        .battery-percentage {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          font-weight: bold;
          font-size: 12px;
          color: var(--primary-text-color);
          text-shadow: 0 0 2px var(--card-background-color);
        }
        .device-stats {
          display: flex;
          justify-content: space-between;
          gap: 8px;
          font-size: 12px;
        }
        .stat {
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        .stat-label {
          color: var(--secondary-text-color);
          margin-bottom: 2px;
        }
        .stat-value {
          font-weight: bold;
        }
        .stat-value.warning {
          color: #ff9800;
        }
        .stat-value.charging {
          color: #4caf50;
        }
        .stat-value.discharging {
          color: #ff9800;
        }
        .total-stats {
          margin-top: 16px;
          padding-top: 12px;
          border-top: 1px solid var(--divider-color);
          text-align: center;
          font-size: 14px;
        }
      </style>
      <ha-card header="Zendure Batterien">
        <div class="card-content">
          <div class="devices-container"></div>
          <div class="total-stats"></div>
        </div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 2 + (this.config.devices?.length || 0);
  }
}

customElements.define('zendure-battery-overview-card', ZendureBatteryOverviewCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'zendure-battery-overview-card',
  name: 'Zendure Battery Overview Card',
  description: 'Zeigt alle Zendure-Batterien übersichtlich mit SoC, Temperatur und Leistung'
});

