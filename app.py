# app.py (completo) - integra todas las funciones previas + las nuevas condiciones solicitadas
from flask import Flask, render_template_string, request, redirect, url_for, send_file, jsonify, Response
import pandas as pd
import matplotlib.pyplot as plt
import io, os, json, urllib.parse, time, tempfile, threading
from datetime import datetime
import datetime as dt

app = Flask(__name__)

# -----------------------
# Configuración / Constantes
# -----------------------
DATA_FILE = "fallas.csv"
COLUMNS = ["id","nombre","numeroEmpleado","linea","machine","failure","startISO","endISO","durationMin","notes","fecha"]

# Password sencillo para borrar todo (puedes cambiarlo o leer de variable de entorno)
CLEAR_PASSWORD = "1234"

# Números de WhatsApp predeterminados (nombre: número con código de país)
NUMEROS_WHATSAPP = {
    "Jose Vitela": "528443434019",
    "Daniel Becerril": "528443507879",
    "Eduardo Salinas": "528446060480",
    "Samuel Gaytan": "528445064299",
    "David Belmares": "528446621177"
}

# Diccionario de líneas y máquinas asociadas
LINEAS_MAQUINAS = {
    "Modulo Flex 2": ["OP90", "OP95", "OP100", "OP110", "OP120", "OP130", "OP140", "OP150", "OP160", "OP170", "OP175", "PACKOUT"],
    "Modulo Flex 1": ["OPFA17", "OPFA16", "OPFA10", "OPFA20", "OPFA15", "OPFA50", "OPFA30", "OPMA010 MARCADO LASER", "OPF010", "OPF011", "OF020", "OPF030", "OPF031", "OPF040", "OPF040", "OPF041", "OPF031", "OPF12 RULADO", "OPF031", "OPFA040", "OPF071", "OPFA060", "OPF100", "OPF101", "OPF115", "OPF116", "PACKOUT"],
    "Modulo EHRS": ["OP10", "OP20-A", "OP20-B", "OP30", "OP40P", "OP40B", "OP40C", "OP50A", "OP50B", "OP50C", "OP60", "PACKOUT"],
    "Modulo GM": ["OP10", "OP20", "OP30", "OP40", "OP45", "OP50", "OP60", "PACKOUT"],
    "Modulo RUWK": ["OP10", "OP21", "OP22", "OP23", "OP30", "OP30 TECDISMA", "OP41", "OP42", "OP51", "OP52", "OP53", "OP60", "OP71", "OP72", "OP80", "PACKOUT"],
    "Cooler RUWK": ["OP09", "OP10", "OP20", "OP30", "OP40", "OP50", "OP60", "OP70", "OP80", "OP90", "OP140", "OP150", "OP150 TECDISMA", "OP100", "OP110", "OP120", "OP130"],
    "Cooler Flex 1": ["OPM15", "OPM20", "OPM21", "OPM22", "OPM30", "OPM40", "OPM50", "OPM51", "OPM60", "OPMA30", "OPMA31", "OPMA20", "OPMA60"],
    "Cooler Flex 2": ["OP10", "OPMA20", "OPMA30", "OPMA40", "OPMA50", "OPMA60", "OPMA70", "OPMA80", "OPMA90 3y4", "OPMA100", "OPMA60A", "OPMA60B", "OPMA60C", "OPMA60D", "OPMA60E", "OPMA901y2"],
    "Cooler Flex 3": ["OP20", "OP21", "OP22", "OP30", "OP40-A", "OP40-B", "OP50", "OP60", "OP100-A", "OP100-B", "OP100-C", "OP100D.A", "OP100D.B", "OP100-E", "OPMA41"],
    "Cooler EHRS": ["OP10", "OP20", "OP30", "OP40", "OP50", "OP60", "OP10-A", "OP10-B", "OP10-C", "OP20-A", "OP30-A", "OP40-A", "OP40-B", "OP50-B"],
    "LINEA - SUBENSAMBLES COOLER": ["CONFORMADO 1", "CONFORMADO 2","CONFORMADO 3","DUNIMEX INLET","DUNIMEX OUTLET", "ITF", "CORTE ORBITAL 1", "CURVADORA 1", "PUNZONADO TUBO OUTLET OP40", "Cortadora tubo outlet OP30", "Aborcadado tubo outlet OP20", "Curvadora 4", "Curvadora 3", "Corte orbital 3", "Silfax 1", "Silfax 2", "Corte vertical 1", "Punzonado EGR", "Punzonado difusor", "Op110", "Op120", "Aborcadado de cyclone", "Corte vertical 2", "Corte vertical 3"],
    "LINEA - HORNOS": ["H1", "H2", "H3","H4"],
    "LINEA - SUBENSAMBLES CYCLONE": ["Opma051", "S100", "OP030", "S100", "S90", "S70", "S50", "S70A soldadora", "S30", "S60", "OP40A","OP40B", "OP80A","OP80B"],
    "LINEA - TUBOS HIBRIDOS": ["TH1", "TH2", "TH3","TH4"],

}

TIPOS_FALLAS = ["Falla eléctrica","Falla Mecanica","Falla Hidraulica","Falla Neumatica","Falla Control Electrico","Falla Control PLC","Falla Camara/Escaner","Otro"]

# -----------------------
# Helpers para datos
# -----------------------
def ensure_datafile():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(DATA_FILE, index=False)

def load_data():
    ensure_datafile()
    try:
        df = pd.read_csv(DATA_FILE)
        # Asegurar que estén las columnas esperadas
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = ""
        return df
    except Exception:
        # Si hay problema al leer, crear vacío
        return pd.DataFrame(columns=COLUMNS)

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def limpiar_fallas_semanales():
    """
    Mantengo la funcionalidad original: al cargar/registrar, se filtran
    y se guardan solo las fallas de la semana actual (si existe campo 'fecha').
    Si no quieres este comportamiento, quítame las llamadas a esta función.
    """
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

# -----------------------
# Plantilla HTML principal (index)
# -----------------------
index_template = r"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <title>Registro de Fallas</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body{ font-family: Arial, sans-serif; margin:0; padding:0; background:#0404b6; color:#f5f5f5; }
    header{ background:#0f176e; padding:12px; color:#f5f5f5; font-weight:bold; text-align:center; }
    .container{ padding:16px; max-width:1200px; margin:12px auto; }
    .form{ display:flex; flex-wrap:wrap; gap:12px; background:#000106; padding:12px; border-radius:8px; }
    .form div{ flex:1; min-width:220px; }
    label{ display:block; margin-bottom:6px; color:#a0aec0; font-weight:bold; }
    input,select,textarea{ width:100%; padding:8px; border-radius:6px; border:none; background:#2b2f48; color:#f5f5f5; }
    textarea{ min-height:100px; }
    button{ padding:10px 14px; border-radius:8px; border:none; cursor:pointer; font-weight:bold; color:#fff; margin:6px 6px 6px 0; }
    .btn-primary{ background:#4cafef; } .btn-green{ background:#00b894; } .btn-orange{ background:#e67e22; } .btn-red{ background:#e74c3c; }
    table{ width:100%; border-collapse:collapse; margin-top:12px; background:#010736; border-radius:8px; overflow:hidden; }
    th,td{ border:1px solid #333; padding:6px; font-size:13px; text-align:left; }
    th{ background:#010736; color:#f5f5f5; }
    tr:nth-child(even){ background:#35384e; } tr:nth-child(odd){ background:#2f3247; }
    .charts{ display:flex; gap:16px; margin-top:16px; flex-wrap:wrap; }
    .chart-container{ background:#010736; padding:12px; border-radius:8px; min-width:300px; flex:1; }
    .small{ font-size:12px; color:#cbd5e1; }
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
        <select id="inputMachine" name="machine" disabled required><option>Selecciona una línea primero</option></select>
      </div>
      <div style="min-width:220px;">
        <label>Tipo de falla</label>
        <select id="inputFailure" name="failure" required>
          <option value="" disabled selected>Seleccionar / escribir</option>
          {% for f in tipos_fallas %}<option>{{ f }}</option>{% endfor %}
        </select>
      </div>
      <div><label>Inicio</label><input type="datetime-local" id="inputStart" name="start" required></div>
      <div><label>Fin</label><input type="datetime-local" id="inputEnd" name="end"></div>
      <div><label>Notas</label><textarea id="inputNotes" name="notes"></textarea></div>

      <div style="flex-basis:100%; text-align:left;">
        <label class="small">Enviar WhatsApp a (opcional)</label>
        <select name="numeroWhatsapp" id="numeroWhatsapp">
          <option value="">-- Selecciona contacto --</option>
          {% for nombre,num in numeros.items() %}
            <option value="{{ num }}">{{ nombre }} ({{ num }})</option>
          {% endfor %}
        </select>
        <label class="small">Otro número (opc.)</label>
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

    <div style="margin-top:10px;">
      <button onclick="clearAll()" class="btn-red">Borrar Todo (servidor)</button>
      <a class="btn-green" href="{{ url_for('preparar_envio') }}">Enviar Reporte WhatsApp (manual)</a>
    </div>

    <table id="dataTable">
      <thead>
        <tr>
          <th>#</th><th>Nombre</th><th>No.Empleado</th><th>Línea</th><th>Máquina</th><th>Falla</th><th>Inicio</th><th>Fin</th><th>Duración (min)</th><th>Notas</th>
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

const el = id => document.getElementById(id);
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
  try{ return new Date(iso).toLocaleString(); }catch(e){ return iso; }
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
  const labels1 = Object.keys(counts), values1 = labels1.map(l=>counts[l]);
  const labels2 = Object.keys(times), values2 = labels2.map(l=>times[l]);

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

// Borrar todo -> pide password (en frontend) y lo envía al servidor para validar
async function clearAll(){
  let pwd = prompt("Introduce el password para borrar:");
  if(pwd === null) return;
  if(!confirm("¿Borrar todos los registros del servidor?")) return;
  const res = await fetch("/clear", { method: "POST", headers: {'Content-Type':'application/json'}, body: JSON.stringify({password: pwd}) });
  if(res.status === 200){ refreshUI(); alert("Datos borrados."); }
  else if(res.status === 403){ alert("Password incorrecto. No se borró nada."); }
  else { alert("Error al borrar. Revisa el servidor."); }
}
</script>
</body>
</html>
"""

# -----------------------
# Rutas
# -----------------------
@app.route("/")
def index():
    limpiar_fallas_semanales()
    return render_template_string(index_template, lineas_maquinas=LINEAS_MAQUINAS, tipos_fallas=TIPOS_FALLAS, numeros=NUMEROS_WHATSAPP)

@app.route("/data")
def data_endpoint():
    df = load_data()
    # devolver lista JSON
    records = df.to_dict(orient="records")
    return jsonify(records)

@app.route("/registrar", methods=["POST"])
def registrar():
    limpiar_fallas_semanales()
    # Leer formulario
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

    df = load_data()
    df = pd.concat([pd.DataFrame([row]), df], ignore_index=True)
    save_data(df)

    # --- WhatsApp AUTOMÁTICO solo si duration > 40 ---
    try:
        dur_val = int(duration) if duration != "" else 0
    except:
        dur_val = 0

    if dur_val and dur_val > 40:
        # determinar destinatarios
        destinatarios = []
        sel = request.form.get("numeroWhatsapp","").strip()
        manual = request.form.get("numeroWhatsappManual","").strip()
        if sel: destinatarios.append(sel)
        if manual:
            m = manual.replace("+","").replace(" ","")
            destinatarios.append(m)
        if not destinatarios:
            destinatarios = list(NUMEROS_WHATSAPP.values())

        # construir mensaje (solo para la falla registrada ahora)
        mensaje = "📋 *Reporte de Falla (Automático)*\n\n"
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

        # devolver HTML que abre los chats (telefónico: whatsapp://send, escritorio: wa.me)
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

    # si no supera 40 min, solo guardar y volver al index
    return redirect(url_for("index"))

@app.route("/importar", methods=["POST"])
def importar():
    file = request.files.get("importFile")
    if not file:
        return redirect(url_for("index"))
    try:
        imported = pd.read_csv(file)
        existing = load_data()
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
    df = load_data()
    table_html = df.to_html(index=False)
    return f"<html><head><meta charset='utf-8'><title>Historial</title></head><body style='font-family:Arial'><h2>Historial de Fallas</h2><div style='max-width:95%;'>{table_html}</div><br><a href='{url_for('index')}'>📝 Registrar Falla</a></body></html>"

@app.route("/grafica")
def grafica():
    df = load_data()
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
    df = load_data()
    # crear archivo temporal (se sobreescribe cada vez con timestamp)
    temp_dir = tempfile.gettempdir()
    fname = f"fallas_export_{int(time.time())}.xlsx"
    temp_file = os.path.join(temp_dir, fname)
    try:
        with pd.ExcelWriter(temp_file, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="fallas")
    except Exception as e:
        return f"Error generando Excel: {e}"
    # borrar el archivo pasado unos segundos para limpieza (hilo separado)
    def _cleanup(path, delay=30):
        def _rm():
            try:
                time.sleep(delay)
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass
        threading.Thread(target=_rm, daemon=True).start()
    _cleanup(temp_file, delay=30)
    return send_file(temp_file, as_attachment=True, download_name="fallas_export.xlsx")

@app.route("/preparar_envio")
def preparar_envio():
    """
    Página que permite seleccionar varias fallas (desde todo el historial)
    y destinatarios para enviar un reporte manual por WhatsApp.
    """
    df = load_data()
    rows_html = ""
    if df.empty:
        rows_html = "<p>No hay fallas registradas.</p>"
    else:
        rows_html += "<form method='post' action='" + url_for("enviar_whatsapp") + "'>"
        rows_html += "<table border='1' style='margin:auto'><tr><th>Enviar</th><th>#</th><th>Nombre</th><th>Empleado</th><th>Línea</th><th>Máquina</th><th>Falla</th><th>Inicio</th><th>Fin</th><th>Duración</th><th>Notas</th></tr>"
        for i, row in df.iterrows():
            rows_html += "<tr>"
            rows_html += f"<td><input type='checkbox' name='selected_ids' value='{row['id']}'></td>"
            rows_html += f"<td>{i+1}</td><td>{row.get('nombre','')}</td><td>{row.get('numeroEmpleado','')}</td><td>{row.get('linea','')}</td><td>{row.get('machine','')}</td><td>{row.get('failure','')}</td>"
            rows_html += f"<td>{row.get('startISO','')}</td><td>{row.get('endISO','')}</td><td>{row.get('durationMin','')}</td><td>{row.get('notes','')}</td>"
            rows_html += "</tr>"
        rows_html += "</table><h3>Destinatarios:</h3>"
        for nombre,num in NUMEROS_WHATSAPP.items():
            rows_html += f"<input type='checkbox' name='destinatarios' value='{num}'> {nombre} ({num})<br>"
        rows_html += "<br>Manual (opcional): <input type='text' name='manual_num' placeholder='Ej: 528449998877'><br><br>"
        rows_html += "<button type='submit'>Enviar WhatsApp</button></form>"
    return f"<html><head><meta charset='utf-8'><title>Preparar Envío</title></head><body style='font-family:Arial;text-align:center'><h2>Selecciona fallas y destinatarios</h2>{rows_html}<br><a href='{url_for('index')}'>Volver</a></body></html>"

@app.route("/enviar_whatsapp", methods=["POST"])
def enviar_whatsapp():
    df = load_data()
    if df.empty:
        return "No hay reportes de fallas registrados."
    selected_ids = request.form.getlist("selected_ids")
    manual_num = request.form.get("manual_num","").strip()
    destinatarios = request.form.getlist("destinatarios")
    if manual_num:
        manual_num = manual_num.replace("+","").replace(" ","")
        destinatarios.append(manual_num)
    if not destinatarios:
        # si no se seleccionó destinatarios, no enviar (seguridad)
        return "No seleccionaste destinatarios."
    if selected_ids:
        df_sel = df[df["id"].astype(str).isin(selected_ids)]
    else:
        return "No seleccionaste fallas para enviar."
    if df_sel.empty:
        return "No hay fallas seleccionadas para enviar."

    mensaje = "📋 *Reporte de Fallas Seleccionadas*\n\n"
    for _, row in df_sel.iterrows():
        start = row.get("startISO") or ""
        end = row.get("endISO") or ""
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
    """
    Endpoint protegido: espera JSON { "password": "..." }
    para borrar. Responde 200 si correcto, 403 si password incorrecto.
    """
    try:
        data = request.get_json(force=True)
    except:
        data = {}
    pwd = (data or {}).get("password","")
    if pwd != CLEAR_PASSWORD:
        return Response("Forbidden", status=403)
    df = pd.DataFrame(columns=COLUMNS)
    df.to_csv(DATA_FILE, index=False)
    return ("OK", 200)

@app.route("/reiniciar_semana", methods=["POST"])
def reiniciar_semana():
    df = pd.DataFrame(columns=COLUMNS)
    df.to_csv(DATA_FILE, index=False)
    return redirect(url_for("historial"))

# -----------------------
# Arranque (Waitress recommended)
# -----------------------
if __name__ == "__main__":
    # Usa waitress para mayor estabilidad en Windows
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=5000)
    except Exception:
        # fallback a Flask dev server si waitress no está instalado
        app.run(host="0.0.0.0", port=5000, debug=False)
