from flask import Flask, render_template, request, redirect, flash, get_flashed_messages
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

# flask
app = Flask(__name__)
app.secret_key = "estadistica2"

# excel
df = pd.read_excel("Datos.xlsx")

@app.route('/')
def index():
    columnas = df.columns.tolist()
    return render_template("index.html", columnas=columnas)

@app.route('/resultado', methods=['POST'])
def resultado():
    analisis = request.form['tipo_analisis']

    if analisis == "medias":
        grupos = df["Tipo de Transporte"].unique().tolist()
        return render_template("resultado.html", analisis=analisis, grupos=grupos)

    elif analisis == "regresion":
        return render_template("resultado_regresion.html", resultado=None)

    elif analisis == "anova":
        return calcular_anova()

    return f"Elegiste el análisis: {analisis}"

#  Comparación de medias validada
@app.route('/calcular_ttest', methods=['POST'])
def calcular_ttest():
    grupo1 = request.form['grupo1']
    grupo2 = request.form['grupo2']

    comparaciones_validas = [
        ("Marítimo", "Terrestre"),
        ("Marítimo", "Aéreo"),
        ("Terrestre", "Aéreo")
    ]

    if grupo1 == grupo2 or (grupo1, grupo2) not in comparaciones_validas and (grupo2, grupo1) not in comparaciones_validas:
        flash("⚠️ Comparación no válida. Solo se permiten combinaciones entre Marítimo, Terrestre y Aéreo.")
        return redirect("/")

    datos1 = df[df["Tipo de Transporte"] == grupo1]["Tiempo de Entrega (días)"]
    datos2 = df[df["Tipo de Transporte"] == grupo2]["Tiempo de Entrega (días)"]

    t_stat, p_value = stats.ttest_ind(datos1, datos2, equal_var=True)

    resultado = {
        "grupo1": grupo1,
        "grupo2": grupo2,
        "media1": round(datos1.mean(), 2),
        "media2": round(datos2.mean(), 2),
        "varianza1": round(datos1.var(ddof=1), 2),
        "varianza2": round(datos2.var(ddof=1), 2),
        "n1": len(datos1),
        "n2": len(datos2),
        "t_stat": round(t_stat, 4),
        "p_value": round(p_value, 4),
        "conclusion": "Se rechaza H0, hay diferencia significativa." if p_value < 0.05 else "No se rechaza H0, no hay diferencia significativa."
    }

    return render_template("resultado_ttest.html", resultado=resultado)

# Regresion Lineal con datos del Excel o manuales
@app.route('/regresion_custom', methods=['POST'])
def regresion_custom():
    modo = request.form['modo']

    if modo == 'excel':
        if 'Experiencia del Personal (años)' not in df.columns or 'Tiempo de Entrega (días)' not in df.columns:
            flash(" El archivo Excel no contiene las columnas necesarias.")
            return redirect("/regresion_lineal")

        X = pd.Series(df["Experiencia del Personal (años)"], name="X")
        y = pd.Series(df["Tiempo de Entrega (días)"], name="Y")

    elif modo == 'manual':
        try:
            x_vals = request.form.getlist('x[]')
            y_vals = request.form.getlist('y[]')

            if len(x_vals) < 2 or len(y_vals) < 2:
                flash("⚠️ Debes ingresar al menos 2 datos para realizar la regresión.")
                return redirect("/regresion_lineal")

            X = pd.Series([float(x) for x in x_vals], name="X")
            y = pd.Series([float(y) for y in y_vals], name="Y")
        except Exception as e:
            flash(f" Error: los datos ingresados no son válidos → {e}")
            return redirect("/regresion_lineal")

    else:
        return redirect("/")

    X = sm.add_constant(X)
    modelo = sm.OLS(y, X).fit()

    intercepto = round(modelo.params["const"], 4)
    pendiente = round(modelo.params["X"], 4)
    r2 = round(modelo.rsquared, 4)
    p_value = round(modelo.pvalues["X"], 4)

    conclusion = "Se rechaza H0. Hay relación significativa." if p_value < 0.05 else \
                 "No se rechaza H0. No hay relación significativa."

    resultado = {
        "pendiente": pendiente,
        "intercepto": intercepto,
        "r2": r2,
        "p_value": p_value,
        "conclusion": conclusion
    }

    return render_template("resultado_regresion.html", resultado=resultado)

@app.route('/regresion_lineal')
def regresion_lineal():
    return render_template("resultado_regresion.html", resultado=None)

# ANOVA
def calcular_anova():
    grupos = df.groupby("Tipo de Transporte")["Tiempo de Entrega (días)"]
    medias_grupo = grupos.mean()
    n_grupos = len(medias_grupo)
    n_total = len(df)

    media_general = df["Tiempo de Entrega (días)"].mean()

    SCG = sum(len(df[df["Tipo de Transporte"] == g]) * (media - media_general) ** 2
              for g, media in medias_grupo.items())

    SCE = sum((x - medias_grupo[g]) ** 2 for g in medias_grupo.index
              for x in df[df["Tipo de Transporte"] == g]["Tiempo de Entrega (días)"])

    SCT = SCG + SCE
    glg = n_grupos - 1
    gle = n_total - n_grupos
    MCG = SCG / glg
    MCE = SCE / gle
    F = MCG / MCE

    from scipy.stats import f
    p_value = 1 - f.cdf(F, glg, gle)

    conclusion = "Se rechaza H0. Hay al menos una diferencia significativa entre los grupos." if p_value < 0.05 else \
                 "No se rechaza H0. No hay diferencias significativas entre los grupos."

    resultado = {
        "SCG": round(SCG, 4),
        "SCE": round(SCE, 4),
        "SCT": round(SCT, 4),
        "MCG": round(MCG, 4),
        "MCE": round(MCE, 4),
        "F": round(F, 4),
        "p_value": round(p_value, 4),
        "glg": glg,
        "gle": gle,
        "conclusion": conclusion,
        "media_general": round(media_general, 2),
        "medias_grupo": medias_grupo.round(2).to_dict()
    }

    return render_template("resultado_anova_manual.html", resultado=resultado)

@app.route('/graficas')
def graficas():
    grupos = df.groupby("Tipo de Transporte")["Tiempo de Entrega (días)"].mean().round(2)
    etiquetas = list(grupos.index)
    medias = list(grupos.values)

    x = df["Experiencia del Personal (años)"].tolist()
    y = df["Tiempo de Entrega (días)"].tolist()

    return render_template("graficas.html", 
        etiquetas=etiquetas,
        medias=medias,
        x=x,
        y=y
    )

@app.route('/datos')
def datos():
    tabla_html = df.to_html(classes='table table-striped table-bordered text-center', index=False)
    return render_template("datos.html", tabla=tabla_html)

if __name__ == '__main__':
    app.run(debug=True)