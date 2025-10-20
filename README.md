# Assistente de Contestação Google Ads — Práticas Comerciais Inaceitáveis

Web app (Streamlit) para:
- Verificar o site (URL ou PDF)
- Gerar relatório de conformidade (score + avisos + riscos)
- Preencher automaticamente todas as respostas do formulário de contestação
- Exportar PDF e JSON
- Interface visual 100% web

## Como rodar (local)
1. Instale Python 3.10+
2. `pip install -r requirements.txt`
3. `streamlit run app.py`
4. Abra o link que o Streamlit mostrar (ex.: http://localhost:8501)

## Como implantar online
- **Streamlit Community Cloud** (grátis): publique o repositório do GitHub e clique “Deploy”
- **Render / Railway / Hugging Face Spaces**: suba o repo e escolha o build com `pip install -r requirements.txt` e start `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

## Observações importantes
- O verificador de site faz análise textual (HTML ou PDF). Para sites com muito JavaScript, exporte um PDF do site e faça upload.
- O assistente é setorial (Contabilidade/Advocacia) e ajusta a linguagem automaticamente.
- Exporte os anexos fora do app e confira se o CNPJ e o WHOIS do domínio batem com a empresa.
- Evite termos de promessa (“garantido”, “aprovado na hora”) em sites/anúncios para maximizar a chance de reativação.

## Estrutura
- `app.py`: aplicativo Streamlit
- `requirements.txt`: dependências
- Exporta: `FormData_[EMPRESA].json`, `Contestacao_[EMPRESA].pdf`