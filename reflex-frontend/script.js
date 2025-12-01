const cardGrid = document.getElementById("card-grid");
const alertsContainer = document.getElementById("alerts");
const chatHistory = document.getElementById("chat-history");
const chatMessage = document.getElementById("chat-message");
const billingStatus = document.getElementById("billing-status");

const USER_ID = 1;
const assistantUrl = "http://localhost:8004/assistant/chat";
const limitsUrl = "http://localhost:8003/limits/summary";
const billingUrl = "http://localhost:8005/billing/me";

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
      `${limitsUrl}?year=${currentYear}&user_id=${USER_ID}`
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

function addChatMessage(author, text) {
  const message = document.createElement("div");
  message.className = `chat-message ${author}`;
  message.innerHTML = `<strong>${author === "user" ? "Você" : "Assistant"}</strong><p>${text}</p>`;
  chatHistory.appendChild(message);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function sendMessage() {
  const text = chatMessage.value.trim();
  if (!text) return;
  addChatMessage("user", text);
  chatMessage.value = "";

  try {
    const response = await fetch(assistantUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID, message: text }),
    });

    if (!response.ok) {
      throw new Error("Falha ao enviar para o assistente");
    }

    const data = await response.json();
    addChatMessage(
      "assistant",
      `${data.reply}\n\nTokens usados: ${data.tokens_used}`
    );
  } catch (error) {
    addChatMessage("assistant", "Não foi possível responder agora. Tente novamente mais tarde.");
    console.error(error);
  }
}

async function loadBilling() {
  billingStatus.innerHTML = "Carregando...";
  try {
    const response = await fetch(`${billingUrl}?user_id=${USER_ID}`);
    if (!response.ok) {
      throw new Error("Falha ao carregar billing");
    }
    const data = await response.json();
    billingStatus.innerHTML = `
      <div class="billing-row">
        <div>
          <p class="muted">Plano</p>
          <h3>${data.plan.name}</h3>
          <p class="muted">Tokens inclusos: ${data.plan.token_limit.toLocaleString("pt-BR")}</p>
        </div>
        <div class="pill">R$ ${data.plan.monthly_price.toLocaleString("pt-BR")}/mês</div>
      </div>
      <div class="progress">
        <div style="width: ${Math.min(
          (data.usage.tokens_used / data.plan.token_limit) * 100,
          100
        )}%"></div>
      </div>
      <p class="muted">Consumo: ${data.usage.tokens_used.toLocaleString("pt-BR")}/${data.plan.token_limit.toLocaleString(
        "pt-BR"
      )} tokens (restantes: ${data.usage.remaining_tokens.toLocaleString("pt-BR")})</p>
      <p class="muted">Uploads: ${data.usage.uploads} • Chamadas API: ${data.usage.api_calls}</p>
    `;
  } catch (error) {
    billingStatus.innerHTML = "Não foi possível carregar as informações de billing.";
    console.error(error);
  }
}

document.getElementById("chat-send").addEventListener("click", sendMessage);
chatMessage.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    sendMessage();
  }
});

document.getElementById("refresh-dashboard").addEventListener("click", loadDashboard);
document.getElementById("refresh-billing").addEventListener("click", loadBilling);

loadDashboard();
loadBilling();
