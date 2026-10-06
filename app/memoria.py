import sqlite3

from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
BANCO_MEMORIA = BASE_DIR.parent / "data" / "memorias.db"


def conectar():
    BANCO_MEMORIA.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(BANCO_MEMORIA)


def criar_banco_memoria():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id TEXT NOT NULL,
            categoria TEXT NOT NULL,
            memoria TEXT NOT NULL,
            importancia INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            ultima_utilizacao TEXT
        )
    """)

    conexao.commit()
    conexao.close()


def adicionar_memoria(
    usuario_id,
    memoria,
    categoria="geral",
    importancia=1
):
    memoria = memoria.strip()

    if not memoria:
        return False

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id
        FROM memorias
        WHERE usuario_id = ?
        AND memoria = ?
    """, (
        str(usuario_id),
        memoria
    ))

    existente = cursor.fetchone()

    if existente:
        cursor.execute("""
            UPDATE memorias
            SET
                importancia = MAX(importancia, ?),
                ultima_utilizacao = ?
            WHERE id = ?
        """, (
            importancia,
            datetime.now().isoformat(),
            existente[0]
        ))

        conexao.commit()
        conexao.close()

        return False

    cursor.execute("""
        INSERT INTO memorias (
            usuario_id,
            categoria,
            memoria,
            importancia,
            criado_em
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        str(usuario_id),
        categoria,
        memoria,
        importancia,
        datetime.now().isoformat()
    ))

    conexao.commit()
    conexao.close()

    return True


def buscar_memorias(
    usuario_id,
    limite=10
):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            id,
            categoria,
            memoria,
            importancia
        FROM memorias
        WHERE usuario_id = ?
        ORDER BY
            importancia DESC,
            ultima_utilizacao DESC
        LIMIT ?
    """, (
        str(usuario_id),
        limite
    ))

    resultados = cursor.fetchall()

    conexao.close()

    return resultados


def construir_contexto_memoria(
    usuario_id,
    limite=10
):
    memorias = buscar_memorias(
        usuario_id,
        limite
    )

    if not memorias:
        return "Nenhuma memória conhecida sobre este usuário."

    texto = []

    for memoria in memorias:
        _, categoria, conteudo, importancia = memoria

        texto.append(
            f"- [{categoria}] {conteudo}"
        )

    return "\n".join(texto)


def remover_memoria(
    usuario_id,
    memoria_id
):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM memorias
        WHERE id = ?
        AND usuario_id = ?
    """, (
        memoria_id,
        str(usuario_id)
    ))

    removeu = cursor.rowcount > 0

    conexao.commit()
    conexao.close()

    return removeu


def editar_memoria(
    usuario_id,
    memoria_id,
    memoria,
    categoria=None,
    importancia=None
):
    memoria = memoria.strip()

    if not memoria:
        return False

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id
        FROM memorias
        WHERE id = ?
        AND usuario_id = ?
    """, (
        memoria_id,
        str(usuario_id)
    ))

    existente = cursor.fetchone()

    if not existente:
        conexao.close()
        return False

    if categoria is None and importancia is None:
        cursor.execute("""
            UPDATE memorias
            SET memoria = ?
            WHERE id = ?
            AND usuario_id = ?
        """, (
            memoria,
            memoria_id,
            str(usuario_id)
        ))

    elif categoria is None:
        cursor.execute("""
            UPDATE memorias
            SET
                memoria = ?,
                importancia = ?
            WHERE id = ?
            AND usuario_id = ?
        """, (
            memoria,
            importancia,
            memoria_id,
            str(usuario_id)
        ))

    elif importancia is None:
        cursor.execute("""
            UPDATE memorias
            SET
                memoria = ?,
                categoria = ?
            WHERE id = ?
            AND usuario_id = ?
        """, (
            memoria,
            categoria,
            memoria_id,
            str(usuario_id)
        ))

    else:
        cursor.execute("""
            UPDATE memorias
            SET
                memoria = ?,
                categoria = ?,
                importancia = ?
            WHERE id = ?
            AND usuario_id = ?
        """, (
            memoria,
            categoria,
            importancia,
            memoria_id,
            str(usuario_id)
        ))

    conexao.commit()

    alterou = cursor.rowcount > 0

    conexao.close()

    return alterou


def listar_memorias(usuario_id):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            id,
            categoria,
            memoria,
            importancia,
            criado_em
        FROM memorias
        WHERE usuario_id = ?
        ORDER BY id DESC
    """, (
        str(usuario_id),
    ))

    resultados = cursor.fetchall()

    conexao.close()

    return resultados


if __name__ == "__main__":
    criar_banco_memoria()

    print("Banco de memória criado com sucesso!")
    print(BANCO_MEMORIA)
