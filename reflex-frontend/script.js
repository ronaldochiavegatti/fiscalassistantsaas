const cardGrid = document.getElementById("card-grid");
const alertsContainer = document.getElementById("alerts");

const fallbackDashboard = {
  revenue_month: 0,
  revenue_year: 0,
  tax_due: 0,
  documents_pending: 0,
  alerts: ["Envie sua primeira nota fiscal para liberar o dashboard."],
};

function renderCards(data) {
  const cards = [
    {
      title: "Faturamento (mês)",
      value: data.revenue_month,
      formatter: (value) => `R$ ${value.toLocaleString("pt-BR")}`,
    },
    {
      title: "Faturamento (ano)",
      value: data.revenue_year,
      formatter: (value) => `R$ ${value.toLocaleString("pt-BR")}`,
    },
    {
      title: "Impostos estimados",
      value: data.tax_due,
      formatter: (value) => `R$ ${value.toLocaleString("pt-BR")}`,
    },
    {
      title: "Documentos pendentes",
      value: data.documents_pending,
      formatter: (value) => `${value} itens`,
    },
  ];

  cardGrid.innerHTML = "";
  cards.forEach((card) => {
    const cardEl = document.createElement("div");
    cardEl.className = "card";
    const value = card.formatter(card.value);
    cardEl.innerHTML = `
      <p class="muted">${card.title}</p>
      <div class="metric">${value}</div>
    `;
    cardGrid.appendChild(cardEl);
  });
}

function renderAlerts(alerts) {
  alertsContainer.innerHTML = "";
  const alertsTitle = document.createElement("h4");
  alertsTitle.textContent = "Alertas";
  alertsContainer.appendChild(alertsTitle);

  alerts.forEach((text) => {
    const item = document.createElement("div");
    item.className = "alert-item";
    item.textContent = text;
    alertsContainer.appendChild(item);
  });
}

async function loadDashboard() {
  const currentYear = new Date().getFullYear();
  let dashboard = { ...fallbackDashboard };

  try {
    const response = await fetch(
      `http://localhost:8003/limits/summary?year=${currentYear}&user_id=1`
    );
    if (!response.ok) {
      throw new Error("Failed to load limits summary");
    }

    const data = await response.json();
    dashboard = {
      revenue_month: data.revenue_month,
      revenue_year: data.revenue_year,
      tax_due: Number((data.revenue_month * 0.08).toFixed(2)),
      documents_pending: 0,
      alerts: [
        `Limite restante MEI: R$ ${data.limit_remaining.toLocaleString("pt-BR", {
          minimumFractionDigits: 2,
        })}`,
        "Envie novas notas fiscais para atualizar o faturamento.",
      ],
    };
  } catch (error) {
    console.warn("Usando dados locais do dashboard", error);
  }

  renderCards(dashboard);
  renderAlerts(dashboard.alerts);
}

loadDashboard();
