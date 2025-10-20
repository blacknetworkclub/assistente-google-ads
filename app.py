
import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import json
import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# -----------------------------
# Helpers
# -----------------------------

def extract_text_from_html(html):
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        text = re.sub(r'\n{2,}', '\n', text)
        return text
    except Exception as e:
        return ""

def fetch_site(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SiteComplianceBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return None

def score_compliance(text, url):
    # Basic checks
    issues = []
    warnings = []
    oks = []

    # HTTPS
    if url.lower().startswith("https://"):
        oks.append("HTTPS ativo")
    else:
        warnings.append("Site sem HTTPS (use HTTPS).")

    # CNPJ
    cnpj_match = re.search(r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b', text)
    if cnpj_match:
        oks.append(f"CNPJ detectado: {cnpj_match.group(0)}")
    else:
        warnings.append("CNPJ não detectado no conteúdo do site.")

    # Contatos
    if re.search(r'@', text) and re.search(r'\b\d{2}\s?\d{4,5}-\d{4}\b', text):
        oks.append("E-mail e telefone encontrados")
    else:
        warnings.append("E-mail e/ou telefone não detectados com clareza.")

    # Políticas
    policies_flags = sum(k in text.lower() for k in ["política de privacidade", "termos de uso", "política de cookies"])
    if policies_flags >= 2:
        oks.append("Políticas (Privacidade/Termos/Cookies) detectadas")
    else:
        warnings.append("Links de políticas não detectados com clareza.")

    # Palavras de risco
    risk_words = [
        "garantido", "100% aprovado", "aprovado na hora", "sem análise", "liberado instantaneamente",
        "sem burocracia", "crédito garantido", "ganhe dinheiro fácil", "resultado garantido"
    ]
    found_risks = [w for w in risk_words if w in text.lower()]
    if found_risks:
        issues.append(f"Palavras de risco detectadas: {', '.join(found_risks)}")
    else:
        oks.append("Sem termos de promessa ou risco (detectados)")

    # Menção explícita a crédito/finanças (para contabilidade/advocacia, deve ser descritivo, não ofertado)
    # Sinalizar como aviso suave
    finance_terms = ["empréstimo", "crédito", "cartão", "aprovação de crédito", "financiamento", "investimento"]
    found_fin = [w for w in finance_terms if w in text.lower()]
    if found_fin:
        warnings.append(f"Termos financeiros detectados: {', '.join(found_fin)} (verifique contexto)")

    # Pontuação simples
    score = 100 - 20*len(issues) - 10*len(warnings)
    score = max(0, min(100, score))
    return score, oks, warnings, issues

def make_pdf(title, sections):
    # sections = list of (heading, text)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 2*cm
    y = height - margin
    c.setTitle(title)

    def draw_text(block_title, block_text):
        nonlocal y
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, block_title)
        y -= 0.6*cm
        c.setFont("Helvetica", 10)
        for line in block_text.split("\n"):
            # automatic page break
            if y < margin + 2*cm:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica-Bold", 12)
                c.drawString(margin, y, block_title + " (cont.)")
                y -= 0.6*cm
                c.setFont("Helvetica", 10)
            c.drawString(margin, y, line[:120])
            y -= 0.5*cm
        y -= 0.3*cm

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, title)
    y -= 1*cm

    for h, t in sections:
        draw_text(h, t)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def sanitize_filename(name):
    return re.sub(r'[^A-Za-z0-9_\-\.]+', '_', name)[:100]

# -----------------------------
# Templates (sector-aware)
# -----------------------------

def contestation_payload(data, site_report):
    empresa = data.get("empresa", "")
    fantasia = data.get("fantasia", "")
    cnpj = data.get("cnpj", "")
    reg_prof = data.get("reg_prof", "")
    tipo = data.get("tipo", "Contabilidade")
    site = data.get("site", "")
    id_ads = data.get("id_ads", "")
    email_ads = data.get("email_ads", "")
    palavras = data.get("palavras_chave", [])
    hoje = datetime.date.today().strftime("%d/%m/%Y")

    # Sector-specific description
    if tipo.lower().startswith("adv"):
        desc = (f"{empresa} é um escritório de advocacia, inscrito {reg_prof} e CNPJ {cnpj}. "
                "Prestamos serviços jurídicos consultivos e contenciosos, com atuação ética e em conformidade com o Estatuto da OAB. "
                "Não ofertamos produtos financeiros, crédito, nem promessas de resultados.")
    else:
        desc = (f"{empresa} é uma empresa de assessoria contábil, registrada {reg_prof} e CNPJ {cnpj}. "
                "Prestamos serviços de contabilidade, planejamento tributário, departamento pessoal e consultoria fiscal. "
                "Não ofertamos crédito, produtos financeiros ou promessas de resultados.")

    acoes = [
        "Revisamos todo o conteúdo do site e removemos quaisquer expressões que pudessem gerar interpretação de promessa de resultado.",
        "Destacamos no rodapé razão social, CNPJ, endereço, canais de contato e links para Política de Privacidade, Termos e Cookies.",
        "Mantemos domínio próprio com SSL/HTTPS ativo e dados de propriedade compatíveis com o CNPJ declarado.",
        "Revisamos anúncios, extensões e palavras-chave para garantir linguagem informativa, sem alegações absolutas."
    ]

    # Assemble form answers
    form = {
        "responsavel_nome": data.get("responsavel", ""),
        "empresa_nome": f"{empresa} (Fantasia: {fantasia})" if fantasia else empresa,
        "id_conta_ads": id_ads,
        "email_conta_ads": email_ads,
        "descricao_empresa": desc,
        "descricao_problema": (
            "Nossa conta foi suspensa por suposta violação da política de Práticas Comerciais Inaceitáveis. "
            "Realizamos auditoria completa e confirmamos a conformidade com as políticas do Google Ads. "
            "Não utilizamos alegações enganosas, redirecionamentos indevidos ou coleta indevida de dados. "
            "Solicitamos revisão manual e reativação da conta."
        ),
        "acoes_corretivas": acoes,
        "site_principal": site,
        "dominio_proprio": "Sim, o domínio pertence integralmente à empresa e os dados de propriedade coincidem com o CNPJ declarado.",
        "outras_contas": "Não. Esta é a única conta usada para anunciar os próprios serviços da empresa.",
        "usa_agencia": "Não. O gerenciamento de campanhas é interno.",
        "palavras_chave": palavras,
        "anexos": [
            "Comprovante de Inscrição e Situação Cadastral (CNPJ) - PDF da Receita Federal",
            "Print de Propriedade do Domínio (WHOIS/painel do registrador)",
            "Comprovante bancário do último pagamento Google Ads",
            "Print da data do último pagamento no painel de faturamento do Google Ads",
            "Print do rodapé do site com razão social, CNPJ e links de políticas",
            "(Opcional) Certidão profissional (CRC/OAB) em PDF"
        ],
        "mensagem_final": (
            "Prezada equipe do Google Ads,\n\n"
            "Após auditoria interna criteriosa, confirmamos que o site e as campanhas estão em conformidade com as políticas do Google Ads. "
            "Implementamos melhorias de transparência e removemos qualquer linguagem que pudesse dar margem a interpretações. "
            "Solicitamos revisão manual e reativação da conta para continuidade de divulgações institucionais, de forma ética e responsável.\n\n"
            f"Atenciosamente,\n{data.get('responsavel','')}\n{empresa}\n{data.get('email_institucional','')}\n{data.get('telefone','')}"
        ),
        "site_score": site_report.get("score", 0),
        "site_warnings": site_report.get("warnings", []),
        "site_issues": site_report.get("issues", []),
        "gerado_em": hoje
    }
    return form

def render_form_text(form):
    # Assemble a human-readable version for copy/paste
    lines = []
    m = form
    lines.append(f"1) Nome do responsável: {m.get('responsavel_nome','')}")
    lines.append(f"2) Empresa: {m.get('empresa_nome','')}")
    lines.append(f"3) ID da conta: {m.get('id_conta_ads','')}")
    lines.append(f"4) E-mail da conta: {m.get('email_conta_ads','')}")
    lines.append("5) Descrição da empresa:")
    lines.append(m.get("descricao_empresa",""))
    lines.append("6) Problema reportado:")
    lines.append(m.get("descricao_problema",""))
    lines.append("7) Ações tomadas:")
    for i, ac in enumerate(m.get("acoes_corretivas", []), 1):
        lines.append(f"   {i}. {ac}")
    lines.append(f"8) Site principal: {m.get('site_principal','')}")
    lines.append(f"9) Domínio pertence à empresa? {m.get('dominio_proprio','')}")
    lines.append(f"10) Outras contas? {m.get('outras_contas','')}")
    lines.append(f"11) Usa agência/parceiro? {m.get('usa_agencia','')}")
    lines.append("12) Palavras-chave:")
    for kw in m.get("palavras_chave", []):
        lines.append(f"   - {kw}")
    lines.append("13) Anexos:")
    for ax in m.get("anexos", []):
        lines.append(f"   - {ax}")
    lines.append("14) Mensagem final:")
    lines.append(m.get("mensagem_final",""))
    lines.append(f"\nScore de conformidade do site: {m.get('site_score',0)}/100")
    if m.get("site_warnings"):
        lines.append("Avisos: " + "; ".join(m.get("site_warnings", [])))
    if m.get("site_issues"):
        lines.append("Riscos: " + "; ".join(m.get("site_issues", [])))
    return "\n".join(lines)

# -----------------------------
# Streamlit UI
# -----------------------------

st.set_page_config(page_title="Assistente de Contestação Google Ads", page_icon="✅", layout="wide")
st.title("Assistente de Contestação Google Ads — Práticas Comerciais Inaceitáveis")

with st.expander("Como funciona", expanded=False):
    st.markdown("""
    1. Preencha os dados da empresa e da conta Google Ads.
    2. Informe o site (URL) **ou** faça upload de um PDF do site.
    3. Clique em **Analisar Site** para gerar o relatório de conformidade.
    4. Preencha/valide as palavras-chave.
    5. Clique em **Gerar Contestação** para criar: respostas do formulário, PDF e JSON.
    """)

st.sidebar.header("Dados da Empresa")
empresa = st.sidebar.text_input("Razão Social", "A J Buchner Assessoria S/S")
fantasia = st.sidebar.text_input("Nome Fantasia", "Buchner Assessoria")
tipo = st.sidebar.selectbox("Tipo de empresa", ["Contabilidade", "Advocacia", "Outro"])
cnpj = st.sidebar.text_input("CNPJ", "51.999.609/0001-57")
reg_prof = st.sidebar.text_input("Registro Profissional (CRC/OAB)", "CRC SC-012740/O")
endereco = st.sidebar.text_input("Endereço", "Servidão Jaborandi, 199 — Campeche, Florianópolis/SC — CEP 88065-035")
telefone = st.sidebar.text_input("Telefone", "(48) 99961-0081")
email_inst = st.sidebar.text_input("E-mail institucional", "contato@iniciofeflds.site")
responsavel = st.sidebar.text_input("Responsável", "João Lucas Buchner")

st.sidebar.header("Conta Google Ads")
id_ads = st.sidebar.text_input("ID da conta Google Ads", "")
email_ads = st.sidebar.text_input("E-mail da conta Ads", "")

st.header("1) Site para verificação")
col1, col2 = st.columns([3,2])
with col1:
    site_url = st.text_input("URL do site", "https://iniciofeflds.site/")
with col2:
    site_pdf = st.file_uploader("Ou faça upload do PDF do site", type=["pdf"])

st.header("2) Palavras-chave (uma por linha)")
default_kws = """serviços de contabilidade
contabilidade em florianópolis
abrir empresa simples nacional
planejamento tributário
assessoria fiscal
escrituração contábil
gestão de folha de pagamento
contabilidade empresarial
consultoria contábil
abrir cnpj
contabilidade para pequenas empresas
contador em florianópolis
abrir mei
consultoria tributária
empresa de contabilidade sc"""
palavras_raw = st.text_area("Palavras-chave", default_kws, height=180)
palavras = [k.strip() for k in palavras_raw.splitlines() if k.strip()]

st.header("3) Analisar Site")
site_text = ""
score = 0
oks = []
warnings = []
issues = []

if st.button("Analisar Site", type="primary"):
    if site_pdf is not None:
        # Try to read the text from PDF via a lightweight approach: ask user to ensure it's text-based
        try:
            import pdfplumber
            with pdfplumber.open(site_pdf) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            site_text = "\n".join(pages)
        except Exception as e:
            st.error("Não foi possível ler o PDF. Envie um PDF com texto ou use a URL.")
            site_text = ""
    else:
        html = fetch_site(site_url)
        if html:
            site_text = extract_text_from_html(html)
        else:
            st.error("Não foi possível acessar a URL. Faça upload do PDF do site.")
            site_text = ""

    if site_text:
        score, oks, warnings, issues = score_compliance(site_text, site_url)
        st.success(f"Análise concluída. Score de conformidade: {score}/100")
        st.subheader("Resultados")
        if oks:
            st.markdown("**Conformes:**")
            for x in oks:
                st.write("✅", x)
        if warnings:
            st.markdown("**Avisos:**")
            for x in warnings:
                st.write("⚠️", x)
        if issues:
            st.markdown("**Riscos:**")
            for x in issues:
                st.write("❌", x)

st.header("4) Gerar Contestação")
if st.button("Gerar Contestação (PDF + JSON + Texto)"):
    data = {
        "empresa": empresa,
        "fantasia": fantasia,
        "tipo": tipo,
        "cnpj": cnpj,
        "reg_prof": reg_prof,
        "endereco": endereco,
        "telefone": telefone,
        "email_institucional": email_inst,
        "responsavel": responsavel,
        "site": site_url,
        "id_ads": id_ads,
        "email_ads": email_ads,
        "palavras_chave": palavras
    }
    site_report = {
        "score": score,
        "oks": oks,
        "warnings": warnings,
        "issues": issues
    }
    form = contestation_payload(data, site_report)
    text_block = render_form_text(form)

    # JSON
    json_bytes = json.dumps(form, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("Baixar JSON (FormData)", data=json_bytes, file_name=f"FormData_{sanitize_filename(empresa)}.json", mime="application/json")

    # PDF
    sections = [
        ("Dados da Empresa", f"{empresa}\nFantasia: {fantasia}\nTipo: {tipo}\nCNPJ: {cnpj}\nRegistro: {reg_prof}\nEndereço: {endereco}\nTelefone: {telefone}\nE-mail: {email_inst}\nResponsável: {responsavel}"),
        ("Conta Google Ads", f"ID: {id_ads}\nE-mail: {email_ads}"),
        ("Site", f"{site_url}\nScore de conformidade: {score}/100"),
        ("Conformes", "\n".join(oks) if oks else "—"),
        ("Avisos", "\n".join(warnings) if warnings else "—"),
        ("Riscos", "\n".join(issues) if issues else "—"),
        ("Descrição da empresa", form['descricao_empresa']),
        ("Problema reportado", form['descricao_problema']),
        ("Ações tomadas", "\n".join([f"{i+1}. {a}" for i,a in enumerate(form['acoes_corretivas'])])),
        ("Palavras-chave", "\n".join(palavras)),
        ("Anexos", "\n".join(form['anexos'])),
        ("Mensagem final", form['mensagem_final'])
    ]
    pdf_buffer = make_pdf(f"Contestacao_{empresa}", sections)
    st.download_button("Baixar PDF (Contestação)", data=pdf_buffer, file_name=f"Contestacao_{sanitize_filename(empresa)}.pdf", mime="application/pdf")

    # Texto copy/paste
    st.subheader("Texto para copiar e colar no formulário")
    st.code(text_block, language="text")

st.caption("Dica: antes de enviar, confira se os anexos batem com o CNPJ e domínio. Evite termos absolutos como 'garantido' e 'aprovado na hora'.")
