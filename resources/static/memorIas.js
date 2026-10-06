const lista = document.getElementById("memories-list");
const contador = document.getElementById("memory-count");

const formulario = document.getElementById("memory-form");
const memoriaInput = document.getElementById("memoria");
const categoriaInput = document.getElementById("categoria");
const importanciaInput = document.getElementById("importancia");

const modal = document.getElementById("edit-modal");
const fecharModal = document.getElementById("close-modal");
const cancelarEdicao = document.getElementById("cancel-edit");

const formularioEdicao = document.getElementById("edit-form");
const editId = document.getElementById("edit-id");
const editMemoria = document.getElementById("edit-memoria");
const editCategoria = document.getElementById("edit-categoria");
const editImportancia = document.getElementById("edit-importancia");


async function carregarMemorias() {
    try {
        const resposta = await fetch("/api/memorias");

        if (!resposta.ok) {
            throw new Error("Não foi possível carregar as memórias.");
        }

        const dados = await resposta.json();

        renderizarMemorias(dados.memorias);

    } catch (erro) {
        lista.innerHTML = `
            <div class="memory-error">
                ❌ ${erro.message}
            </div>
        `;

        contador.textContent = "Erro ao carregar memórias.";
    }
}


function renderizarMemorias(memorias) {

    contador.textContent = `${memorias.length} memória${memorias.length === 1 ? "" : "s"} salva${memorias.length === 1 ? "" : "s"}`;

    if (memorias.length === 0) {
        lista.innerHTML = `
            <div class="memory-empty">
                <div class="memory-empty-icon">🧠</div>

                <h3>Nenhuma memória ainda</h3>

                <p>
                    Guy ainda não possui nenhuma informação
                    salva sobre você.
                </p>
            </div>
        `;

        return;
    }

    lista.innerHTML = "";

    memorias.forEach(memoria => {

        const card = document.createElement("div");

        card.className = "memory-card";

        const estrelas = "⭐".repeat(
            Math.max(
                1,
                Math.min(
                    5,
                    Number(memoria.importancia) || 1
                )
            )
        );

        const data = formatarData(
            memoria.criado_em
        );

        card.innerHTML = `
            <div class="memory-card-content">

                <div class="memory-card-top">

                    <span class="memory-category">
                        ${escaparHTML(memoria.categoria)}
                    </span>

                    <span class="memory-importance">
                        ${estrelas}
                    </span>

                </div>

                <p class="memory-text-content">
                    ${escaparHTML(memoria.memoria)}
                </p>

                <span class="memory-date">
                    Criada em ${data}
                </span>

            </div>

            <div class="memory-actions">

                <button
                    class="memory-edit"
                    data-id="${memoria.id}"
                >
                    ✏️ Editar
                </button>

                <button
                    class="memory-delete"
                    data-id="${memoria.id}"
                >
                    🗑️ Apagar
                </button>

            </div>
        `;

        lista.appendChild(card);
    });

    document.querySelectorAll(".memory-edit").forEach(botao => {

        botao.addEventListener("click", () => {

            const id = Number(botao.dataset.id);

            const memoria = memorias.find(
                item => item.id === id
            );

            if (memoria) {
                abrirEdicao(memoria);
            }
        });
    });


    document.querySelectorAll(".memory-delete").forEach(botao => {

        botao.addEventListener("click", () => {

            const id = Number(botao.dataset.id);

            apagarMemoria(id);
        });
    });
}


formulario.addEventListener("submit", async evento => {

    evento.preventDefault();

    const memoria = memoriaInput.value.trim();
    const categoria = categoriaInput.value;
    const importancia = Number(
        importanciaInput.value
    );

    if (!memoria) {
        return;
    }

    const botao = formulario.querySelector(
        "button[type='submit']"
    );

    botao.disabled = true;
    botao.textContent = "Adicionando...";

    try {

        const resposta = await fetch(
            "/api/memorias",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    memoria,
                    categoria,
                    importancia
                })
            }
        );

        const dados = await resposta.json();

        if (!resposta.ok) {
            throw new Error(
                dados.detail ||
                "Erro ao adicionar memória."
            );
        }

        formulario.reset();

        importanciaInput.value = "3";

        await carregarMemorias();

    } catch (erro) {

        alert(erro.message);

    } finally {

        botao.disabled = false;
        botao.textContent = "+ Adicionar";
    }
});


function abrirEdicao(memoria) {

    editId.value = memoria.id;

    editMemoria.value = memoria.memoria;

    editCategoria.value =
        memoria.categoria;

    editImportancia.value =
        memoria.importancia;

    modal.classList.remove("hidden");

    setTimeout(() => {
        editMemoria.focus();
    }, 50);
}


function fecharEdicao() {
    modal.classList.add("hidden");
}


fecharModal.addEventListener(
    "click",
    fecharEdicao
);

cancelarEdicao.addEventListener(
    "click",
    fecharEdicao
);


document.querySelector(
    ".modal-overlay"
).addEventListener(
    "click",
    fecharEdicao
);


document.addEventListener(
    "keydown",
    evento => {

        if (
            evento.key === "Escape" &&
            !modal.classList.contains("hidden")
        ) {
            fecharEdicao();
        }
    }
);


formularioEdicao.addEventListener(
    "submit",
    async evento => {

        evento.preventDefault();

        const id = editId.value;

        const memoria =
            editMemoria.value.trim();

        const categoria =
            editCategoria.value;

        const importancia =
            Number(editImportancia.value);

        if (!memoria) {
            return;
        }

        const botao =
            formularioEdicao.querySelector(
                "button[type='submit']"
            );

        botao.disabled = true;
        botao.textContent = "Salvando...";

        try {

            const resposta = await fetch(
                `/api/memorias/${id}`,
                {
                    method: "PUT",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        memoria,
                        categoria,
                        importancia
                    })
                }
            );

            const dados =
                await resposta.json();

            if (!resposta.ok) {
                throw new Error(
                    dados.detail ||
                    "Erro ao editar memória."
                );
            }

            fecharEdicao();

            await carregarMemorias();

        } catch (erro) {

            alert(erro.message);

        } finally {

            botao.disabled = false;
            botao.textContent =
                "Salvar alterações";
        }
    }
);


async function apagarMemoria(id) {

    const confirmar = confirm(
        "Tem certeza que deseja apagar esta memória?"
    );

    if (!confirmar) {
        return;
    }

    try {

        const resposta = await fetch(
            `/api/memorias/${id}`,
            {
                method: "DELETE"
            }
        );

        const dados =
            await resposta.json();

        if (!resposta.ok) {
            throw new Error(
                dados.detail ||
                "Erro ao apagar memória."
            );
        }

        await carregarMemorias();

    } catch (erro) {

        alert(erro.message);
    }
}


function formatarData(data) {

    if (!data) {
        return "data desconhecida";
    }

    try {

        return new Date(data).toLocaleString(
            "pt-BR",
            {
                dateStyle: "short",
                timeStyle: "short"
            }
        );

    } catch {

        return data;
    }
}


function escaparHTML(texto) {

    const div =
        document.createElement("div");

    div.textContent =
        String(texto ?? "");

    return div.innerHTML;
}


document.addEventListener(
    "DOMContentLoaded",
    carregarMemorias
);

