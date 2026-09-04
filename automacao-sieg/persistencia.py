import io

import json
from datetime import datetime
from googleapiclient.http import MediaIoBaseUpload
from config import DRIVE_RELATORIOS_FOLDER_ID
from config import ARQUIVO_CHECKPOINT, PASTA_REGISTROS


def _agora():
    return datetime.now()


def _garantir_pastas():
    PASTA_REGISTROS.mkdir(parents=True, exist_ok=True)


def _ler_checkpoint_do_dia():
    hoje = _agora().date().isoformat()
    if not ARQUIVO_CHECKPOINT.exists():
        return {"data": hoje, "processados": []}

    try:
        dados = json.loads(ARQUIVO_CHECKPOINT.read_text(encoding="utf-8"))
        if dados.get("data") != hoje or not isinstance(dados.get("processados"), list):
            return {"data": hoje, "processados": []}
        return dados
    except (OSError, ValueError, TypeError):
        return {"data": hoje, "processados": []}


def carregar_cnpjs_processados():
    """Retorna os CNPJs concluídos com sucesso na data atual."""
    dados = _ler_checkpoint_do_dia()
    return {
        item.get("cnpj") if isinstance(item, dict) else item
        for item in dados["processados"]
        if (isinstance(item, str) and item) or (isinstance(item, dict) and item.get("cnpj"))
    }


def registrar_cnpj_processado(cnpj, nome):
    """Registra um sucesso de forma atômica para permitir retomada."""
    _garantir_pastas()
    dados = _ler_checkpoint_do_dia()
    processados = dados["processados"]
    if not any(
        (item.get("cnpj") if isinstance(item, dict) else item) == cnpj
        for item in processados
    ):
        processados.append({
            "cnpj": cnpj,
            "nome": nome,
            "processado_em": _agora().isoformat(timespec="seconds"),
        })

    temporario = ARQUIVO_CHECKPOINT.with_suffix(".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(ARQUIVO_CHECKPOINT)


def adicionar_falha(falhas_detalhes, page, cnpj, nome, motivo):
    """Acrescenta a falha ao resumo da execução."""
    falhas_detalhes.append({
        "cnpj": cnpj,
        "nome": nome,
        "motivo": str(motivo),
    })


def gerar_resumo_execucao(
    sucessos,
    falhas_detalhes,
    ignorados,
    service,
    empresas_sucesso=None,
    quantidade_certas=0,
):
    """Gera o relatório JSON e envia diretamente para o Google Drive."""
    agora = _agora()

    nome_arquivo = (
        f"resumo_{agora.strftime('%Y%m%d_%H%M%S')}.json"
    )

    relatorio = {
        "titulo": "RESUMO DA AUTOMAÇÃO SIEG",
        "executado_em": agora.isoformat(timespec="seconds"),
        "resumo": {
            "sucessos": sucessos,
            "ignorados": ignorados,
            "falhas": len(falhas_detalhes),
            "certas": quantidade_certas,
        },
        "empresas_com_falha": falhas_detalhes,
        "empresas_com_sucesso": empresas_sucesso or [],
    }

    json_bytes = json.dumps(
        relatorio,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    arquivo_memoria = io.BytesIO(json_bytes)

    media = MediaIoBaseUpload(
        arquivo_memoria,
        mimetype="application/json",
        resumable=False,
    )

    arquivo_drive = service.files().create(
        body={
            "name": nome_arquivo,
            "parents": [DRIVE_RELATORIOS_FOLDER_ID],
        },
        media_body=media,
        fields="id, name, webViewLink",
        supportsAllDrives=True,
    ).execute()

    # O novo resumo já foi salvo; agora remove somente os resumos anteriores.
    query = (
        f"'{DRIVE_RELATORIOS_FOLDER_ID}' in parents "
        "and trashed=false "
        "and name contains 'resumo_'"
    )
    page_token = None
    resumos_anteriores = []
    while True:
        resultado = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        for arquivo in resultado.get("files", []):
            nome = arquivo.get("name", "")
            if (
                arquivo.get("id") != arquivo_drive["id"]
                and nome.startswith("resumo_")
                and nome.endswith(".json")
            ):
                resumos_anteriores.append(arquivo)

        page_token = resultado.get("nextPageToken")
        if not page_token:
            break

    for arquivo in resumos_anteriores:
        service.files().delete(
            fileId=arquivo["id"],
            supportsAllDrives=True,
        ).execute()

    return arquivo_drive
