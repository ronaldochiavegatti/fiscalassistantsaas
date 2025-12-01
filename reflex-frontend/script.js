const cardGrid = document.getElementById("card-grid");
const alertsContainer = document.getElementById("alerts");

const mockDashboard = {
  revenue_month: 12500,
  revenue_year: 74200,
  tax_due: 1850,
  documents_pending: 3,
  alerts: [
    "Envie as notas fiscais do último trimestre.",
    "Valide o faturamento do mês passado para evitar multas.",
  ],
};

const cards = [
  {
    title: "Faturamento (mês)",
    value: mockDashboard.revenue_month,
    formatter: (value) => `R$ ${value.toLocaleString("pt-BR")}`,
  },
  {
    title: "Faturamento (ano)",
    value: mockDashboard.revenue_year,
    formatter: (value) => `R$ ${value.toLocaleString("pt-BR")}`,
  },
  {
    title: "Impostos estimados",
    value: mockDashboard.tax_due,
    formatter: (value) => `R$ ${value.toLocaleString("pt-BR")}`,
  },
  {
    title: "Documentos pendentes",
    value: mockDashboard.documents_pending,
    formatter: (value) => `${value} itens`,
  },
];

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

const alertsTitle = document.createElement("h4");
alertsTitle.textContent = "Alertas";
alertsContainer.appendChild(alertsTitle);

mockDashboard.alerts.forEach((text) => {
  const item = document.createElement("div");
  item.className = "alert-item";
  item.textContent = text;
  alertsContainer.appendChild(item);
});
