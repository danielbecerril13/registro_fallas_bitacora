from flask import Flask, render_template_string, request, redirect, url_for, send_file
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

# Diccionario de líneas y máquinas (recortado para legibilidad; agregar el resto si hace falta)
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
    "LINEA - SUBENSAMBLES CYCLONE": ["Opma051", "S100", "OP030", "S100", "S90", "S70", "S50", "S70A soldadora", "S30", "S60", "OP40A","OP40B", "OP80A","OP80B"],
    "LINEA - TUBOS HIBRIDOS": ["TH1", "TH2", "TH3","TH4"],
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

# ================= Templates (tema fijo) =================
form_template = r"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <title>Registro de Fallas</title>
  <script>
    const lineas_maquinas = {{ lineas_maquinas|tojson }};
    function actualizarMaquinas(){
      let linea = document.getElementById('linea').value;
      let sel = document.getElementById('machine');
      sel.innerHTML = '';
      if(!linea) { sel.disabled=true; sel.innerHTML='<option>Selecciona una línea primero</option>'; return; }
      sel.disabled=false;
      lineas_maquinas[linea].forEach(m=>{
        let o=document.createElement('option'); o.value=m; o.textContent=m; sel.appendChild(o);
      });
    }
    function triggerImport(){ document.getElementById('importFile').click(); }
  </script>
  <style>
    body{ font-family: Arial, sans-serif; margin:0; padding:0; background:#19bfc9; color:#f5f5f5; text-align:center; }
    header{ background:#0f176e; padding:12px; color:#f5f5f5; font-weight:bold; border-radius:8px 8px 0 0; }
    .container{ padding:16px; max-width:1100px; margin:12px auto; }
    .form{ display:flex; flex-wrap:wrap; gap:12px; background:#000106; padding:12px; border-radius:8px; }
    .form div{ flex:1; min-width:220px; }
    input,select,textarea{ width:100%; padding:8px; border-radius:6px; border:none; background:#2b2f48; color:#f5f5f5; }
    textarea{ min-height:120px; }
    button{ padding:10px 14px; border-radius:8px; border:none; cursor:pointer; background:#4cafef; color:#fff; font-weight:bold; }
    .button-like{ display:inline-block; margin:8px; padding:8px 12px; background:#00b894; color:#fff; border-radius:8px; text-decoration:none; }
    table{ width:100%; border-collapse:collapse; margin-top:12px; background:#010736; color:#fff; }
    th,td{ border:1px solid #333; padding:6px; font-size:13px; text-align:left; }
  </style>
</head>
<body>
  <header>📊 Registro de Fallas BorgWarner Thermal</header>
  <div class="container">
    <form class="form" method="post" action="{{ url_for('registrar') }}">
      <div><label>Nombre</label><input name="nombre" required></div>
      <div><label>No. Empleado</label><input name="numeroEmpleado" required></div>
      <div>
        <label>Línea de Producción</label>
        <select id="linea" name="linea" onchange="actualizarMaquinas()" required>
          <option value="">Selecciona línea</option>
          {% for l in lineas %}<option value="{{l}}">{{l}}</option>{% endfor %}
        </select>
      </div>
      <div>
        <label>Máquina</label>
        <select id="machine" name="machine" disabled required><option>Selecciona una línea primero</option></select>
      </div>
      <div>
        <label>Tipo de falla</label>
        <select name="failure" required>
          <option value="">Seleccionar / escribir</option>
          {% for f in tipos_fallas %}<option>{{f}}</option>{% endfor %}
        </select>
      </div>
      <div><label>Inicio</label><input type="datetime-local" name="start" required></div>
      <div><label>Fin</label><input type="datetime-local" name="end"></div>
      <div style="min-width:260px"><label>Notas (grande)</label><textarea name="notes"></textarea></div>
      <div style="flex-basis:100%; text-align:left;">
        <label>Enviar WhatsApp a:</label>
        <select name="numeroWhatsapp">
          <option value="">-- Selecciona --</option>
          {% for nombre, num in numeros.items() %}<option value="{{num}}">{{nombre}} ({{num}})</option>{% endfor %}
        </select>
        <label>Otro número (opcional)</label>
        <input name="numeroWhatsappManual" placeholder="Ej: 528449998877">
      </div>
      <div style="flex-basis:100%; text-align:left;">
        <button type="submit">Registrar Falla</button>
        <button type="button" onclick="triggerImport()">Importar CSV</button>
        <form id="importForm" method="post" action="{{ url_for('importar') }}" enctype="multipart/form-data" style="display:inline-block;">
          <input id="importFile" name="importFile" type="file" accept=".csv" style="display:none" onchange="document.getElementById('importForm').submit();">
        </form>
        <a class="button-like" href="{{ url_for('exportar') }}">Exportar a Excel</a>
        <a class="button-like" href="{{ url_for('historial') }}">Ver Historial</a>
        <a class="button-like" href="{{ url_for('grafica') }}">Ver Gráfica</a>
      </div>
    </form>
    <hr/>
    <p>Nota: la app guarda los registros y cada semana se eliminan los registros de semanas anteriores automáticamente.</p>
  </div>
</body>
</html>
"""

confirm_template = r"""
<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Confirmación</title></head>
<body style="font-family:Arial;text-align:center;">
  <h2>✅ Reporte registrado con éxito</h2>
  <form method="get" action="{{ url_for('preparar_envio') }}"><button type="submit">📲 Preparar envío de WhatsApp</button></form><br>
  <a href="{{ url_for('historial') }}">📑 Ver Historial</a>
</body></html>
"""

preparar_envio_template = r"""
<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Preparar Envío</title></head><body style="font-family:Arial;">
  <h2 style="text-align:center">Selecciona fallas y destinatarios</h2>
  <form method="post" action="{{ url_for('enviar_whatsapp') }}">
    <h3>Fallas del día (selecciona las que quieras enviar)</h3>
    {% if df_today.empty %}<p>No hay fallas hoy.</p>{% else %}
      <table border="1" style="margin:auto"><tr><th>Enviar</th><th>#</th><th>Nombre</th><th>Empleado</th><th>Línea</th><th>Máquina</th><th>Falla</th><th>Inicio</th><th>Fin</th><th>Notas</th></tr>
        {% for i,row in df_today.iterrows() %}
        <tr>
          <td><input type="checkbox" name="selected_ids" value="{{row['id']}}" checked></td>
          <td>{{ loop.index }}</td><td>{{ row['nombre'] }}</td><td>{{ row['numeroEmpleado'] }}</td><td>{{ row['linea'] }}</td><td>{{ row['machine'] }}</td><td>{{ row['failure'] }}</td>
          <td>{{ row['startISO'] if row.get('startISO') else row.get('start','') }}</td>
          <td>{{ row['endISO'] if row.get('endISO') else row.get('end','') }}</td>
          <td>{{ row['notes'] }}</td>
        </tr>
        {% endfor %}
      </table>
    {% endif %}
    <h3>Selecciona destinatarios</h3>
    {% for nombre, num in numeros.items() %}<input type="checkbox" name="destinatarios" value="{{num}}"> {{nombre}} ({{num}}) <br>{% endfor %}
    <br><label>Enviar también a (manual):</label><br><input type="text" name="manual_num" placeholder="Ej: 528449998877"><br><br>
    <button type="submit">Enviar WhatsApp a los seleccionados</button>
  </form>
  <div style="text-align:center"><a href="{{ url_for('index') }}">Volver</a></div>
</body></html>
"""

historial_template = r"""
<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Historial</title></head>
<body style="font-family:Arial;text-align:center;"><h2>Historial de Fallas</h2>
  <div style="max-width:95%; margin:auto;">{{ table|safe }}</div><br>
  <a href="{{ url_for('index') }}">📝 Registrar Falla</a> | <a href="{{ url_for('grafica') }}">📊 Ver Gráfica</a> | <a href="{{ url_for('exportar') }}">📥 Exportar a Excel</a>
  <br><br>
  <form action="{{ url_for('reiniciar_semana') }}" method="post" onsubmit="return confirm('¿Seguro que quieres reiniciar (borrar) la semana?');"><button type="submit">Reiniciar Semana</button></form>
</body></html>
"""

# ================= RUTAS =================
@app.route("/")
def index():
    limpiar_fallas_semanales()
    return render_template_string(form_template, lineas=list(LINEAS_MAQUINAS.keys()), lineas_maquinas=LINEAS_MAQUINAS, tipos_fallas=TIPOS_FALLAS, numeros=NUMEROS_WHATSAPP)

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
    return render_template_string(confirm_template)

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
    return render_template_string(historial_template, table=table_html)

@app.route("/grafica")
def grafica():
    df = pd.read_csv(DATA_FILE)
    if df.empty:
        return "No hay datos para graficar"
    counts = df["linea"].value_counts()
    plt.figure(figsize=(8,5))
    counts.plot(kind="bar", color='skyblue')
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
    return render_template_string(preparar_envio_template, df_today=df_today, numeros=NUMEROS_WHATSAPP)

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
        if n.startswith("52") or n.startswith("+52"):
            n_clean = n.replace("+","")
        else:
            if n.startswith("0"):
                n_clean = "52" + n.lstrip("0")
            elif len(n) == 10 and n.isdigit():
                n_clean = "52" + n
            else:
                n_clean = n
        enlaces.append(f"https://wa.me/{n_clean}?text={mensaje_enc}")

    html_open = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Enviando...</title></head><body><h3 style='text-align:center'>Abriendo chats de WhatsApp...</h3><script>\n"
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
setTimeout(()=>{ document.body.innerHTML += "<p style='text-align:center'>Si no se abren automáticamente, haz click en los enlaces abajo:</p>"; enlaces.forEach(u=>document.body.innerHTML += '<p style="text-align:center"><a href="'+u+'" target="_blank">'+u+'</a></p>'); }, enlaces.length*900 + 400);
</script></body></html>"""
    return html_open

@app.route("/reiniciar_semana", methods=["POST"])
def reiniciar_semana():
    df = pd.DataFrame(columns=COLUMNS)
    df.to_csv(DATA_FILE, index=False)
    return redirect(url_for("historial"))

if __name__ == "__main__":
    app.run(debug=True)
