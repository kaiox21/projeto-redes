// NetMon: painel web. Conversa com o servidor só por HTTP (fetch), consultando a cada 2 segundos.
"use strict";

const INTERVALO_MS = 2000;
let ultimoAlerta = 0;     // maior id de alerta já mostrado
let temporizador = null;

function el(id) {
  return document.getElementById(id);
}

// Coloca um texto vindo do servidor dentro do HTML sem que ele vire código.
function seguro(valor) {
  const div = document.createElement("div");
  div.textContent = valor === null || valor === undefined ? "" : String(valor);
  return div.innerHTML;
}

function emMs(valor) {
  return valor === null ? "—" : valor.toFixed(1) + " ms";
}

// Faz uma requisição HTTP e devolve {status, dados}. O cookie de sessão vai junto automaticamente.
async function pedir(metodo, rota, corpo) {
  const opcoes = { method: metodo };
  if (corpo) {
    opcoes.headers = { "Content-Type": "application/json" };
    opcoes.body = JSON.stringify(corpo);
  }
  const resposta = await fetch(rota, opcoes);
  const dados = await resposta.json();
  return { status: resposta.status, dados: dados };
}

// ------------------------------------------------------------ login e saída
el("form-login").addEventListener("submit", async function (evento) {
  evento.preventDefault();
  const form = new FormData(evento.target);
  const r = await pedir("POST", "/api/login", { usuario: form.get("usuario"), senha: form.get("senha") });
  if (r.status === 200) {
    abrirPainel(r.dados.usuario);
  } else {
    el("erro-login").textContent = r.dados.erro;
    el("erro-login").hidden = false;
  }
});

el("btn-sair").addEventListener("click", async function () {
  await pedir("POST", "/api/logout");
  fecharPainel("");
});

async function abrirPainel(usuario) {
  el("usuario-atual").textContent = usuario;
  el("tela-login").hidden = true;
  el("tela-painel").hidden = false;
  el("erro-login").hidden = true;
  ultimoAlerta = 0;
  el("lista-alertas").innerHTML = "";
  await carregarRegras();
  await atualizar();
  temporizador = setInterval(atualizar, INTERVALO_MS);
}

function fecharPainel(mensagem) {
  clearInterval(temporizador);
  el("tela-painel").hidden = true;
  el("tela-login").hidden = false;
  if (mensagem) {
    el("erro-login").textContent = mensagem;
    el("erro-login").hidden = false;
  }
}

// ------------------------------------------------------------ consulta periódica
async function atualizar() {
  const inicio = performance.now();
  try {
    const alvos = await pedir("GET", "/api/alvos");
    if (alvos.status === 401) {
      fecharPainel("Sessão encerrada. Entre novamente.");
      return;
    }
    const agentes = await pedir("GET", "/api/agentes");
    const alertas = await pedir("GET", "/api/alertas?desde=" + ultimoAlerta);
    el("tempo-resposta").textContent = (performance.now() - inicio).toFixed(1) + " ms";
    el("status-servidor").textContent = "servidor no ar";
    el("status-servidor").className = "selo up";
    mostrarAlvos(alvos.dados);
    mostrarAgentes(agentes.dados);
    mostrarAlertas(alertas.dados);
  } catch (erro) {
    // servidor fora do ar: o painel continua tentando a cada 2 s
    el("status-servidor").textContent = "servidor indisponível";
    el("status-servidor").className = "selo down";
    el("tempo-resposta").textContent = "—";
  }
}

function mostrarAlvos(alvos) {
  if (alvos.length === 0) return;
  let html = "";
  for (const m of alvos) {
    html += "<tr><td>" + seguro(m.alvo) + "</td>" +
      '<td><span class="selo ' + (m.estado === "UP" ? "up" : "down") + '">' + m.estado + "</span></td>" +
      "<td>" + emMs(m.tcp_ms) + "</td><td>" + emMs(m.http_ms) + "</td>" +
      "<td>" + seguro(m.agente_id) + "</td><td>" + seguro(m.ts) + "</td></tr>";
  }
  el("tabela-alvos").innerHTML = html;

  // mantém a lista de alvos do filtro do histórico atualizada
  const select = document.querySelector("#form-historico select");
  for (const m of alvos) {
    let existe = false;
    for (const opcao of select.options) {
      if (opcao.value === m.alvo) existe = true;
    }
    if (!existe) select.add(new Option(m.alvo, m.alvo));
  }
}

function mostrarAgentes(agentes) {
  let html = "";
  for (const a of agentes) {
    html += '<li><span class="selo ' + (a.online ? "up" : "cinza") + '">' + (a.online ? "online" : "offline") +
      "</span> " + seguro(a.agente_id) + "</li>";
  }
  el("lista-agentes").innerHTML = html;
}

function mostrarAlertas(alertas) {
  // a API devolve do mais novo para o mais antigo; mostramos o mais novo no topo
  for (let i = alertas.length - 1; i >= 0; i--) {
    const a = alertas[i];
    const li = document.createElement("li");
    li.className = a.nivel;
    li.innerHTML = "<small>" + seguro(a.ts) + " · " + seguro(a.nivel) + "</small><br>" + seguro(a.mensagem);
    el("lista-alertas").prepend(li);
    ultimoAlerta = Math.max(ultimoAlerta, a.id);
  }
}

// ------------------------------------------------------------ regras (configuração por HTTP PUT)
const NOMES_REGRAS = {
  fora_do_ar: "fora do ar",
  tcp_ms: "conexão TCP acima de",
  http_ms: "resposta HTTP acima de",
};

async function carregarRegras() {
  const r = await pedir("GET", "/api/regras");
  let html = "";
  for (const regra of r.dados) {
    const limiar = regra.metrica === "fora_do_ar"
      ? '<input type="hidden" name="limiar" value="0">—'
      : '<input type="number" step="any" name="limiar" value="' + regra.limiar + '">';
    html += '<tr data-id="' + regra.id + '"><td>' + regra.id + "</td><td>" + NOMES_REGRAS[regra.metrica] + "</td>" +
      "<td>" + limiar + "</td>" +
      '<td><input type="number" name="consecutivas" min="1" max="100" value="' + regra.consecutivas + '"></td>' +
      '<td><select name="nivel"><option' + (regra.nivel === "aviso" ? " selected" : "") + ">aviso</option>" +
      "<option" + (regra.nivel === "critico" ? " selected" : "") + ">critico</option></select></td>" +
      '<td><button class="sec">Salvar</button></td></tr>';
  }
  el("tabela-regras").innerHTML = html;

  for (const linha of el("tabela-regras").querySelectorAll("tr")) {
    linha.querySelector("button").addEventListener("click", async function (evento) {
      const corpo = {
        limiar: Number(linha.querySelector("[name=limiar]").value),
        consecutivas: Number(linha.querySelector("[name=consecutivas]").value),
        nivel: linha.querySelector("[name=nivel]").value,
      };
      const r = await pedir("PUT", "/api/regras/" + linha.dataset.id, corpo);
      evento.target.textContent = r.status === 200 ? "Salvo" : "Erro " + r.status;
      setTimeout(function () { evento.target.textContent = "Salvar"; }, 1500);
    });
  }
}

// ------------------------------------------------------------ histórico
el("form-historico").addEventListener("submit", async function (evento) {
  evento.preventDefault();
  const alvo = new FormData(evento.target).get("alvo");
  const inicio = performance.now();
  const r = await pedir("GET", "/api/medicoes?limite=200" + (alvo ? "&alvo=" + encodeURIComponent(alvo) : ""));
  let html = "";
  for (const m of r.dados) {
    html += "<tr><td>" + seguro(m.ts) + "</td><td>" + seguro(m.alvo) + "</td><td>" + m.estado + "</td>" +
      "<td>" + emMs(m.tcp_ms) + "</td><td>" + emMs(m.http_ms) + "</td><td>" + seguro(m.agente_id) + "</td></tr>";
  }
  el("tabela-historico").innerHTML = html;
  el("info-historico").textContent = r.dados.length + " medições · resposta HTTP em " +
    (performance.now() - inicio).toFixed(1) + " ms";
});
