from flask import Flask, render_template_string, request, redirect, url_for, send_file, jsonify
import pandas as pd
import matplotlib.pyplot as plt
import io, os, json, urllib.parse, time
from datetime import datetime
import datetime as dt

app = Flask(__name__)

DATA_FILE = "fallas.csv"
COLUMNS = ["id","nombre","numeroEmpleado","linea","machine","failure","startISO","endISO","durationMin","notes","fecha"]

# Números de WhatsApp predeterminados (nombre: número con código de país)
NUMEROS_WHATSAPP = {
    "Jose Vitela": "528443434019",
    "Daniel Becerril": "528443507879",
    "Eduardo Salinas": "528446060480",
    "Samuel Gaytan": "528445064299",
    "David Belmares": "528446621177"
}

# Diccionario líneas -> máquinas (usé la lista larga que compartiste)
LINEAS_MAQUINAS = {
  "LINEA - SUBENSAMBLES COOLER": ["CONFORMADO 1","CONFORMADO 2","CONFORMADO 3"],
  "LINEA - SUBENSAMBLES CYCLONE": ["OP020","OP030"],
  "LINEA - MODULO FLEX 1": ["FA017","FA016","FA010","FA020","OP015","FA050","FA030","MA010 MARCADO COOLER","F010","F011","F020","F030","F031","F040","F041","F012","FA040","F090","FA060","F100","F101","F115","F116","OP-PACKOUT"],
  "LINEA - MODULO FLEX 2": ["OPF090","OPF095","OP100","OP110","OP120","OP130","OP140","OP150","OP160","OP170","OP175","OP180","OP-PACKOUT"],
  "LINEA - MODULO EHRS": ["OP10","OP20-1","OP20-2","OP30","OP40B","OP40C","OP40P","OP50A","OP50B","OP50C","OP60","OP-PACKOUT"],
  "LINEA - MODULO GM": ["F010","F020","F030","F040","F045","F050","F060","F080","F090"],
  "LINEA - MODULO RUWK": ["OP10","OP21","OP22","OP23","OP30","OP30 TECDISMA","OP41","OP42","OP51","OP52","OP53","OP60B","OP71","OP72","OP80","OP-PACKOUT"],
  "LINEA - COOLER RUWK": ["OP09","OP10","OP20","OP30","OP40","OP50","OP60","OP70","OP80","OP90","OP140","OP150","OP150 TECDISMA","OP100","OP110","OP120","OP130"],
  "LINEA - COOLER FLEX 1": ["OPM015","OPM020","OPM021","OPM022","OPM030","OPM040","OPM051","OPM050","OPM060","OPMA030","OPMA031","OPMA020","OPMA060","OP-GAGE"],
  "LINEA - COOLER FLEX 2": ["OP10","OPMA020","OPMA030","OPMA040","OPMA050","OPMA060","OPMA070","OPMA090 3y4","OPMA100","OPMA060A","OPMA060B","OPMA060C","OPMA060D","OPMA060E","OPMA090 1y2"],
  "LINEA - COOLER EHRS": ["OP10","OP20","OP30","OP40","OP50","OP60","OP10-A","OP10-B","OP10-C","OP20-A","OP30-A","OP40-A","OP40-B","OP50-B"],
  "LINEA - COOLER FLEX 3": ["OP20","OP21","OP22","OP30","OP40-A","OP40-B","OP50","OP60","OP100-A","OP100-B","OP100-C","OP100-D.A","OP100-D.B","OP100-E","OPMA41"],
  "LINEA - TUBOS HIBRIDOS": ["TH1","TH2","TH3","TH4"],
  # agregué unos nombres cortos también (si los necesitas puedes ajustar)
  "Modulo Flex 2": ["OP90","OP95","OP100","OP110","OP120","OP130","OP140","OP150","OP160","OP170","OP175","OP-PACKOUT"],
  "Modulo Flex 1": ["FA017","FA016","FA010","FA020","OP015","FA050","FA030","MA010 MARCADO COOLER","F010","F011","F020","F030","F031","F040","F041","F012","FA040","F090","FA060","F100","F101","F115","F116","OP-PACKOUT"]
}

TIPOS_FALLAS = ["Falla eléctrica","Falla Mecanica","Falla Hidraulica","Falla Neumatica","Falla Control Electrico","Falla Control PLC","Falla Camara/Escaner","Otro"]

def ensure_datafile():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(DATA_FILE, index=False)

ensure_datafile()

def limpiar_fallas_semanales():
    ensure_datafile()
    df = pd.read_csv(DATA_FILE)
    if df.empty:
        return
    if "fecha" not in df.columns:
        return
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    semana_actual = dt.datetime.now().isocalendar().week
    año_actual = dt.datetime.now().year
    df = df[(df["fecha"].dt.isocalendar().week == semana_actual) & (df["fecha"].dt.year == año_actual)]
    df.to_csv(DATA_FILE, index=False)

def parse_datetime_input(val):
    if not isinstance(val, str) or not val.strip():
        return None, ""
    try:
        if "T" in val:
            dtobj = datetime.fromisoformat(val)
        else:
            hoy = datetime.now().date()
            dtobj = datetime.combine(hoy, datetime.strptime(val, "%H:%M").time())
        return dtobj, dtobj.isoformat()
    except Exception:
        return None, val

# ----------------- Plantilla HTML (index) -----------------
index_template = r"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>Registro de Fallas</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { font-family: Arial, sans-serif; margin:0; padding:0; background:#0404b6; color:#f5f5f5; }
    header { background:#0f176e; padding:15px; text-align:center; font-size:22px; font-weight:bold; color:#f5f5f5; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
    .container { padding:20px; max-width:1100px; margin:0 auto; }
    .form { display:flex; flex-wrap:wrap; gap:15px; margin-bottom:20px; background:#000106; padding:15px; border-radius:10px; }
    .form div { flex:1; min-width:220px; }
    label { display:block; margin-bottom:5px; font-weight:bold; color:#a0aec0; }
    input, select, textarea { width:100%; padding:8px; border-radius:6px; border:none; background:#3a3f5c; color:#fff; }
    textarea { resize:vertical; min-height:80px; }
    button { margin:5px 5px 5px 0; padding:10px 15px; border:none; border-radius:6px; cursor:pointer; font-weight:bold; color:#fff; }
    .btn-primary { background:#4cafef; }
    .btn-green { background:#00b894; }
    .btn-orange { background:#e67e22; }
    .btn-red { background:#e74c3c; }
    table { width:100%; border-collapse:collapse; margin-top:15px; background:#010736; border-radius:10px; overflow:hidden; }
    th, td { border:1px solid #444; padding:6px; text-align:left; font-size:13px; }
    th { background:#010736; color:#f5f5f5; }
    tr:nth-child(even) { background:#35384e; }
    tr:nth-child(odd) { background:#2f3247; }
    .charts { display:flex; flex-wrap:wrap; gap:20px; margin-top:20px; }
    .chart-container { flex:1; min-width:300px; background:#010736; padding:15px; border-radius:10px; }
    .small { font-size:12px; color:#cbd5e1; }
    .top-actions { margin-bottom:10px; }
  </style>
</head>
<body>
  <header>📊 Registro de Fallas BorgWarner Thermal</header>
  <div class="container">
    <form id="mainForm" class="form" method="post" action="{{ url_for('registrar') }}">
      <div><label>Nombre</label><input name="nombre" id="inputNombre" required></div>
      <div><label>No. Empleado</label><input name="numeroEmpleado" id="inputNumeroEmpleado" required></div>
      <div>
        <label>Línea de Producción</label>
        <select id="inputLinea" name="linea" required>
          <option value="" disabled selected>Selecciona línea</option>
        </select>
      </div>
      <div>
        <label>Máquina</label>
        <select id="inputMachine" name="machine" disabled required>
          <option value="">Selecciona una línea primero</option>
        </select>
      </div>
      <div style="flex:1;min-width:220px">
        <label>Tipo de falla</label>
        <select id="inputFailure" name="failure" required>
          <option value="" disabled selected>Seleccionar / escribir</option>
          {% for f in tipos_fallas %}<option>{{f}}</option>{% endfor %}
        </select>
      </div>
      <div><label>Inicio</label><input type="datetime-local" id="inputStart" name="start" required></div>
      <div><label>Fin</label><input type="datetime-local" id="inputEnd" name="end"></div>
      <div><label>Notas</label><textarea id="inputNotes" name="notes"></textarea></div>

      <!-- Opciones WhatsApp (si quieres controlar destinatarios) -->
      <div style="flex-basis:100%; text-align:left;">
        <label class="small">Enviar WhatsApp a (opcional):</label>
        <select name="numeroWhatsapp" id="numeroWhatsapp">
          <option value="">-- Selecciona contacto -- (si dejas vacío enviará a todos los contactos por defecto)</option>
          {% for nombre,num in numeros.items() %}
            <option value="{{ num }}">{{ nombre }} ({{ num }})</option>
          {% endfor %}
        </select>
        <label class="small">Otro número (opcional, formato: 521XXXXXXXXXX o 528XXXXXXXXXX)</label>
        <input name="numeroWhatsappManual" id="numeroWhatsappManual" placeholder="Ej: 528449998877">
      </div>

      <div style="flex-basis:100%; text-align:left;">
        <button type="submit" class="btn-primary">Registrar Falla</button>
        <button type="button" class="btn-green" onclick="document.getElementById('importFile').click()">Importar CSV</button>
        <a class="btn-orange" href="{{ url_for('exportar') }}">Exportar Excel</a>
        <a class="btn-orange" href="{{ url_for('historial') }}">Ver Historial</a>
      </div>
    </form>

    <form id="importForm" method="post" action="{{ url_for('importar') }}" enctype="multipart/form-data" style="display:none;">
      <input id="importFile" name="importFile" type="file" accept=".csv" onchange="document.getElementById('importForm').submit();">
    </form>

    <div class="top-actions">
      <button onclick="clearAll()" class="btn-red">Borrar Todo (servidor)</button>
    </div>

    <table id="dataTable">
      <thead>
        <tr>
          <th>#</th><th>Nombre</th><th>No.Empleado</th>
          <th>Línea</th><th>Máquina</th><th>Falla</th>
          <th>Inicio</th><th>Fin</th><th>Duración (min)</th><th>Notas</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>

    <div class="charts">
      <div class="chart-container"><canvas id="chartFailures"></canvas></div>
      <div class="chart-container"><canvas id="chartDowntime"></canvas></div>
    </div>
  </div>

<script>
const lineas = {{ lineas_maquinas|tojson }};
const tiposFallas = {{ tipos_fallas|tojson }};
const numerosWhatsapp = {{ numeros|tojson }};

const el = id=>document.getElementById(id);
function llenarLineas(){
  const sel = el("inputLinea");
  Object.keys(lineas).forEach(l=>{
    let opt=document.createElement("option"); opt.value=l; opt.textContent=l; sel.appendChild(opt);
  });
}
el("inputLinea").onchange = ()=>{
  let linea = el("inputLinea").value;
  let sel = el("inputMachine");
  sel.innerHTML="";
  if(!linea){
    sel.disabled=true;
    sel.innerHTML='<option>Selecciona una línea primero</option>';
  }else{
    sel.disabled=false;
    lineas[linea].forEach(m=>{
      let opt=document.createElement("option"); opt.value=m; opt.textContent=m; sel.appendChild(opt);
    });
  }
};

llenarLineas();

async function fetchData(){
  const res = await fetch("/data");
  return res.json();
}

function formatDate(iso){
  if(!iso) return "";
  try{
    return new Date(iso).toLocaleString();
  }catch(e){ return iso; }
}

function renderTable(data){
  const tbody = document.querySelector("#dataTable tbody");
  tbody.innerHTML="";
  data.forEach((r,i)=>{
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${i+1}</td>
      <td>${r.nombre||""}</td>
      <td>${r.numeroEmpleado||""}</td>
      <td>${r.linea||""}</td>
      <td>${r.machine||""}</td>
      <td>${r.failure||""}</td>
      <td>${formatDate(r.startISO)}</td>
      <td>${formatDate(r.endISO)}</td>
      <td>${r.durationMin??""}</td>
      <td>${r.notes||""}</td>`;
    tbody.appendChild(tr);
  });
}

let chartFailures, chartDowntime;
function renderCharts(data){
  const counts = {};
  const times = {};
  data.forEach(r=>{
    const f = r.failure || "Sin tipo";
    counts[f] = (counts[f]||0)+1;
    if(r.durationMin) times[f] = (times[f]||0) + Number(r.durationMin);
  });
  const labels1 = Object.keys(counts);
  const values1 = labels1.map(l=>counts[l]);
  const labels2 = Object.keys(times);
  const values2 = labels2.map(l=>times[l]);

  const ctx1 = el("chartFailures").getContext("2d");
  const ctx2 = el("chartDowntime").getContext("2d");
  if(chartFailures) chartFailures.destroy();
  if(chartDowntime) chartDowntime.destroy();
  chartFailures = new Chart(ctx1, { type: "bar", data: { labels: labels1, datasets: [{ label: "Cantidad", data: values1 }] } });
  chartDowntime = new Chart(ctx2, { type: "bar", data: { labels: labels2, datasets: [{ label: "Tiempo muerto (min)", data: values2 }] } });
}

async function refreshUI(){
  const data = await fetchData();
  renderTable(data);
  renderCharts(data);
}
refreshUI();

// llamada automática: cuando el form se envía por POST, el servidor guarda y devuelve una página que abre los enlaces de WhatsApp.
// Aquí solo actualizamos UI si el usuario no es redirigido.
document.getElementById("mainForm").addEventListener("submit", ()=>{ /* submit normal */ });

async function clearAll(){
  if(!confirm("¿Borrar todos los registros del servidor?")) return;
  const res = await fetch("/clear", { method: "POST" });
  if(res.ok){ refreshUI(); alert("Datos borrados."); }
}
</script>
</body>
</html>
"""

# ----------------- Rutas -----------------
@app.route("/")
def index():
    limpiar_fallas_semanales()
    return render_template_string(index_template, lineas_maquinas=LINEAS_MAQUINAS, tipos_fallas=TIPOS_FALLAS, numeros=NUMEROS_WHATSAPP)

@app.route("/data")
def data_endpoint():
    df = pd.read_csv(DATA_FILE)
    # convertir a lista de dicts
    records = df.to_dict(orient="records")
    return jsonify(records)

@app.route("/registrar", methods=["POST"])
def registrar():
    limpiar_fallas_semanales()
    nombre = request.form.get("nombre","").strip()
    numeroEmpleado = request.form.get("numeroEmpleado","").strip()
    linea = request.form.get("linea","").strip()
    machine = request.form.get("machine","").strip()
    failure = request.form.get("failure","").strip()
    notes = request.form.get("notes","").strip()

    start_raw = request.form.get("start","")
    end_raw = request.form.get("end","")
    start_dt, start_iso = parse_datetime_input(start_raw)
    end_dt, end_iso = parse_datetime_input(end_raw)

    duration = ""
    if start_dt and end_dt:
        duration = int((end_dt - start_dt).total_seconds() // 60)

    id_val = int(time.time()*1000)
    row = {
        "id": id_val,
        "nombre": nombre,
        "numeroEmpleado": numeroEmpleado,
        "linea": linea,
        "machine": machine,
        "failure": failure,
        "startISO": start_iso,
        "endISO": end_iso,
        "durationMin": duration,
        "notes": notes,
        "fecha": datetime.now().strftime("%Y-%m-%d")
    }
    df = pd.read_csv(DATA_FILE)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)

    # --- Lógica para enviar WhatsApp AUTOMÁTICAMENTE después de guardar ---
    # Determinar destinatarios: si se escogió uno en el formulario o se puso número manual.
    destinatarios = []
    sel = request.form.get("numeroWhatsapp","").strip()
    manual = request.form.get("numeroWhatsappManual","").strip()
    if sel:
        destinatarios.append(sel)
    if manual:
        # limpiar caracteres comunes
        m = manual.replace("+","").replace(" ","")
        destinatarios.append(m)
    # Si no se proporcionó ningún destinatario, enviar a todos los contactos predeterminados
    if not destinatarios:
        destinatarios = list(NUMEROS_WHATSAPP.values())

    # Construir mensaje (mismo formato que antes)
    mensaje = "📋 *Reporte de Fallas*\n\n"
    s = ""
    e = ""
    try:
        s = datetime.fromisoformat(start_iso).strftime("%Y-%m-%d %H:%M") if start_iso else ""
    except:
        s = start_iso or ""
    try:
        e = datetime.fromisoformat(end_iso).strftime("%Y-%m-%d %H:%M") if end_iso else ""
    except:
        e = end_iso or ""
    mensaje += f"👤 {nombre} (Emp {numeroEmpleado})\n"
    mensaje += f"🏭 {linea} | ⚙️ {machine}\n"
    mensaje += f"❌ {failure}\n"
    mensaje += f"⏱️ {s} - {e} ({duration} min)\n"
    mensaje += f"📝 {notes}\n"
    mensaje += "-------------------------\n"
    mensaje_enc = urllib.parse.quote(mensaje)

    enlaces = []
    for num in destinatarios:
        n = str(num).strip()
        if n.startswith("+"):
            n = n.replace("+","")
        if n.startswith("52"):
            n_clean = n
        else:
            if n.startswith("0"):
                n_clean = "52" + n.lstrip("0")
            elif len(n) == 10 and n.isdigit():
                n_clean = "52" + n
            else:
                n_clean = n
        enlaces.append(f"https://wa.me/{n_clean}?text={mensaje_enc}")

    # Devolver HTML que abrirá los chats (comportamiento móvil: whatsapp://send)
    html_open = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Enviando...</title></head><body style='font-family:Arial;text-align:center;'><h3>📲 Abriendo chats de WhatsApp...</h3><p>Si no se abren automáticamente, aparecerán los enlaces debajo.</p><script>\n"
    html_open += "let enlaces = " + json.dumps(enlaces) + ";\n"
    html_open += """
function esMovil(){ return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent); }
enlaces.forEach((url,idx)=>{
  setTimeout(()=>{
    if(esMovil()){
      try{
        let parts = url.replace("https://wa.me/","").split("?text=");
        let phone = parts[0]; let text = parts[1] || "";
        let appUrl = "whatsapp://send?phone=" + phone + "&text=" + text;
        window.open(appUrl, "_blank");
      }catch(e){ window.open(url,"_blank"); }
    } else {
      window.open(url,"_blank");
    }
  }, idx*800);
});
setTimeout(()=>{ document.body.innerHTML += "<hr><div>"; enlaces.forEach(u=>document.body.innerHTML += '<p><a href="'+u+'" target="_blank">'+u+'</a></p>'); document.body.innerHTML += '</div>'; }, enlaces.length*800 + 400);
</script></body></html>
"""
    return html_open

@app.route("/importar", methods=["POST"])
def importar():
    file = request.files.get("importFile")
    if not file:
        return redirect(url_for("index"))
    try:
        imported = pd.read_csv(file)
        existing = pd.read_csv(DATA_FILE)
        # intentar concatenar columnas compatibles
        common = [c for c in imported.columns if c in existing.columns]
        if not common:
            return "CSV no compatible (no se encontraron columnas comunes)."
        merged = pd.concat([existing, imported[common]], ignore_index=True, sort=False)
        merged.to_csv(DATA_FILE, index=False)
    except Exception as e:
        return f"Error al importar CSV: {e}"
    return redirect(url_for("index"))

@app.route("/historial")
def historial():
    df = pd.read_csv(DATA_FILE)
    table_html = df.to_html(index=False)
    return f"<html><head><meta charset='utf-8'><title>Historial</title></head><body style='font-family:Arial'><h2>Historial de Fallas</h2><div style='max-width:95%;'>{table_html}</div><br><a href='{url_for('index')}'>📝 Registrar Falla</a></body></html>"

@app.route("/grafica")
def grafica():
    df = pd.read_csv(DATA_FILE)
    if df.empty:
        return "No hay datos para graficar"
    counts = df["linea"].value_counts()
    plt.figure(figsize=(8,5))
    counts.plot(kind="bar")
    plt.title("Fallas por Línea")
    plt.xlabel("Línea")
    plt.ylabel("Cantidad")
    plt.xticks(rotation=45)
    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format="png")
    plt.close()
    img.seek(0)
    return send_file(img, mimetype="image/png")

@app.route("/exportar")
def exportar():
    df = pd.read_csv(DATA_FILE)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="fallas")
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="fallas_export.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/preparar_envio")
def preparar_envio():
    df = pd.read_csv(DATA_FILE)
    hoy = datetime.now().strftime("%Y-%m-%d")
    df_today = df[df["fecha"] == hoy] if "fecha" in df.columns else df
    # pagina simple para seleccionar y enviar manualmente
    rows_html = ""
    if df_today.empty:
        rows_html = "<p>No hay fallas hoy.</p>"
    else:
        rows_html = "<form method='post' action='" + url_for("enviar_whatsapp") + "'>"
        rows_html += "<table border='1' style='margin:auto'><tr><th>Enviar</th><th>#</th><th>Nombre</th><th>Empleado</th><th>Línea</th><th>Máquina</th><th>Falla</th><th>Inicio</th><th>Fin</th><th>Notas</th></tr>"
        for i, row in df_today.iterrows():
            rows_html += "<tr>"
            rows_html += f"<td><input type='checkbox' name='selected_ids' value='{row['id']}' checked></td>"
            rows_html += f"<td>{i+1}</td><td>{row.get('nombre','')}</td><td>{row.get('numeroEmpleado','')}</td><td>{row.get('linea','')}</td><td>{row.get('machine','')}</td><td>{row.get('failure','')}</td>"
            rows_html += f"<td>{row.get('startISO','')}</td><td>{row.get('endISO','')}</td><td>{row.get('notes','')}</td>"
            rows_html += "</tr>"
        rows_html += "</table><h3>Destinatarios:</h3>"
        for nombre,num in NUMEROS_WHATSAPP.items():
            rows_html += f"<input type='checkbox' name='destinatarios' value='{num}' checked> {nombre} ({num})<br>"
        rows_html += "<br>Manual: <input type='text' name='manual_num' placeholder='Ej: 528449998877'><br><button type='submit'>Enviar WhatsApp</button></form>"
    return f"<html><head><meta charset='utf-8'><title>Preparar Envío</title></head><body style='font-family:Arial;text-align:center'><h2>Selecciona fallas y destinatarios</h2>{rows_html}<br><a href='{url_for('index')}'>Volver</a></body></html>"

@app.route("/enviar_whatsapp", methods=["POST"])
def enviar_whatsapp():
    df = pd.read_csv(DATA_FILE)
    if df.empty:
        return "No hay reportes de fallas registrados."
    selected_ids = request.form.getlist("selected_ids")
    manual_num = request.form.get("manual_num","").strip()
    destinatarios = request.form.getlist("destinatarios")
    if manual_num:
        manual_num = manual_num.replace("+","").replace(" ","")
        destinatarios.append(manual_num)
    if not destinatarios:
        return "No seleccionaste destinatarios."
    if selected_ids:
        df_sel = df[df["id"].astype(str).isin(selected_ids)]
    else:
        hoy = datetime.now().strftime("%Y-%m-%d")
        df_sel = df[df["fecha"] == hoy] if "fecha" in df.columns else df
    if df_sel.empty:
        return "No hay fallas seleccionadas para enviar."

    mensaje = "📋 *Reporte de Fallas*\n\n"
    for _, row in df_sel.iterrows():
        start = row.get("startISO") or row.get("start","")
        end = row.get("endISO") or row.get("end","")
        try:
            s = datetime.fromisoformat(start).strftime("%Y-%m-%d %H:%M") if start else ""
        except:
            s = start
        try:
            e = datetime.fromisoformat(end).strftime("%Y-%m-%d %H:%M") if end else ""
        except:
            e = end
        mensaje += f"👤 {row.get('nombre','')} (Emp {row.get('numeroEmpleado','')})\n"
        mensaje += f"🏭 {row.get('linea','')} | ⚙️ {row.get('machine','')}\n"
        mensaje += f"❌ {row.get('failure','')}\n"
        mensaje += f"⏱️ {s} - {e} ({row.get('durationMin','')} min)\n"
        mensaje += f"📝 {row.get('notes','')}\n"
        mensaje += "-------------------------\n"
    mensaje_enc = urllib.parse.quote(mensaje)

    enlaces = []
    for num in destinatarios:
        n = num.strip()
        if n.startswith("+"):
            n = n.replace("+","")
        if n.startswith("52"):
            n_clean = n
        else:
            if n.startswith("0"):
                n_clean = "52" + n.lstrip("0")
            elif len(n) == 10 and n.isdigit():
                n_clean = "52" + n
            else:
                n_clean = n
        enlaces.append(f"https://wa.me/{n_clean}?text={mensaje_enc}")

    html_open = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Enviando...</title></head><body style='font-family:Arial;text-align:center;'><h3>📲 Abriendo chats de WhatsApp...</h3><script>\n"
    html_open += "let enlaces = " + json.dumps(enlaces) + ";\n"
    html_open += """
function esMovil(){ return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent); }
enlaces.forEach((url,idx)=>{
  setTimeout(()=>{
    if(esMovil()){
      try{
        let parts = url.replace("https://wa.me/","").split("?text=");
        let phone = parts[0]; let text = parts[1] || "";
        let appUrl = "whatsapp://send?phone=" + phone + "&text=" + text;
        window.open(appUrl, "_blank");
      }catch(e){ window.open(url,"_blank"); }
    } else {
      window.open(url,"_blank");
    }
  }, idx*900);
});
setTimeout(()=>{ document.body.innerHTML += "<p>Si no se abren automáticamente, haz click en los enlaces abajo:</p>"; enlaces.forEach(u=>document.body.innerHTML += '<p><a href="'+u+'" target="_blank">'+u+'</a></p>'); }, enlaces.length*900 + 400);
</script></body></html>"""
    return html_open

@app.route("/clear", methods=["POST"])
def clear():
    df = pd.DataFrame(columns=COLUMNS)
    df.to_csv(DATA_FILE, index=False)
    return ("OK", 200)

@app.route("/reiniciar_semana", methods=["POST"])
def reiniciar_semana():
    df = pd.DataFrame(columns=COLUMNS)
    df.to_csv(DATA_FILE, index=False)
    return redirect(url_for("historial"))

if __name__ == "__main__":
    # escucha en todas las interfaces para que sea accesible en la red local
    app.run(host="0.0.0.0", port=5000, debug=True)
