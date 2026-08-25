// Cole aqui o ID da pasta e-CNPJ visto no endereço do navegador.
const PASTA_E_CNPJ_ID = "COLE_AQUI_O_ID_DA_PASTA";

// Mantenha true no primeiro teste. Nesse modo, nada é criado.
const MODO_SIMULACAO = true;


function converterSenhasParaTxt() {
  if (PASTA_E_CNPJ_ID === "COLE_AQUI_O_ID_DA_PASTA") {
    throw new Error("Preencha PASTA_E_CNPJ_ID antes de executar.");
  }

  const pastaPrincipal = DriveApp.getFolderById(PASTA_E_CNPJ_ID);
  const pastasEmpresas = pastaPrincipal.getFolders();

  let documentosEncontrados = 0;
  let arquivosQueSeriamCriados = 0;
  let pastasComTxt = 0;
  let documentosVazios = 0;
  let erros = 0;

  while (pastasEmpresas.hasNext()) {
    const pastaEmpresa = pastasEmpresas.next();

    try {
      if (possuiSenhaTxt(pastaEmpresa)) {
        console.log(
          `IGNORADO - já possui senha.txt: ${pastaEmpresa.getName()}`
        );
        pastasComTxt++;
        continue;
      }

      const documentos = pastaEmpresa.getFilesByType(
        MimeType.GOOGLE_DOCS
      );

      while (documentos.hasNext()) {
        const arquivoGoogleDocs = documentos.next();
        const nome = arquivoGoogleDocs.getName().trim().toLowerCase();

        if (!nome.startsWith("senha")) {
          continue;
        }

        documentosEncontrados++;

        const documento = DocumentApp.openById(
          arquivoGoogleDocs.getId()
        );
        const conteudo = documento.getBody().getText().trim();

        if (!conteudo) {
          console.log(
            `IGNORADO - documento vazio: ${pastaEmpresa.getName()}`
          );
          documentosVazios++;
          break;
        }

        if (MODO_SIMULACAO) {
          console.log(
            `SIMULAÇÃO - criaria senha.txt em: ${pastaEmpresa.getName()}`
          );
        } else {
          pastaEmpresa.createFile(
            "senha.txt",
            conteudo,
            MimeType.PLAIN_TEXT
          );
          console.log(
            `CRIADO - senha.txt em: ${pastaEmpresa.getName()}`
          );
        }

        arquivosQueSeriamCriados++;

        // Usa apenas o primeiro Google Docs de senha encontrado na pasta.
        break;
      }
    } catch (erro) {
      console.log(`ERRO - ${pastaEmpresa.getName()}: ${erro.message}`);
      erros++;
    }
  }

  console.log("---------------------------");
  console.log(`Modo de simulação: ${MODO_SIMULACAO}`);
  console.log(`Google Docs encontrados: ${documentosEncontrados}`);
  console.log(`Arquivos que seriam criados: ${arquivosQueSeriamCriados}`);
  console.log(`Pastas que já possuem TXT: ${pastasComTxt}`);
  console.log(`Documentos vazios: ${documentosVazios}`);
  console.log(`Erros: ${erros}`);
}


function possuiSenhaTxt(pastaEmpresa) {
  const arquivos = pastaEmpresa.getFiles();

  while (arquivos.hasNext()) {
    const arquivo = arquivos.next();
    const nome = arquivo.getName().trim().toLowerCase();

    if (nome === "senha.txt") {
      return true;
    }
  }

  return false;
}
