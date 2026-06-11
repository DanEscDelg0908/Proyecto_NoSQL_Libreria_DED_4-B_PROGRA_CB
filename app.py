!pip install streamlit pymongo dnspython

%%writefile app.py
import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
import pandas as pd
from datetime import datetime

@st.cache_resource
def conectar_db():
  mongo_uri = st.secrets["mongo"]["uri"]
  cliente = MongoClient(mongo_uri)
  return cliente["Libreria"]

base_datos = conectar_db()

st.set_page_config(page_title="Libreria de MongoDB", layout="wide")

#Para la barra lateral
st.sidebar.title("📚 Sistema de la Libreria")
nombre_coleccion = st.sidebar.selectbox("Selecciona una Colección: ", ["Libros", "Clientes", "Ventas"])
coleccion = base_datos[nombre_coleccion]

st.title(f"Gestión de: {nombre_coleccion}")

#Para la Configuración de los campos que se van a utilizar
campos_por_coleccion = {
    "Libros": ["Título", "Autor", "Precio", "Stock"],
    "Clientes": ["Nombre", "Email", "Teléfono"],
    "Ventas": ["Libro", "Cliente", "Total", "Fecha"]
}

#Para crear las pestañas
pestanas = st.tabs(["📊Dashboard","👀Ver Datos", "➕ Agregar", "🛒Ticket", "🗑 Eliminar"])

#Obtener todos los datos de la Coleccion seleccionada
lista_datos = list(coleccion.find())

#Dashboard (La Grafica)
with pestanas[0]:
    st.subheader("📈 Análisis de los Libros Más Vendidos")

    #Se extrae los datos de las colecciones
    coleccion_ventas = base_datos["Ventas"]
    coleccion_libros = base_datos["Libros"]

    lista_ventas = list(coleccion_ventas.find())
    lista_libros = list(coleccion_libros.find())

    if lista_ventas and lista_libros:
        #Se convierten las colecciones en DataFrames de Pandas
        df_ventas = pd.DataFrame(lista_ventas)
        df_libros = pd.DataFrame(lista_libros)

        #Se verifica que el campo clave 'productos' y 'totalventa' existan en la colección
        if 'productos' in df_ventas.columns and 'totalventa' in df_ventas.columns:
            #1. Nos aseguramos de que 'totalventa' sea numérico para hacer operaciones
            df_ventas['totalventa'] = pd.to_numeric(df_ventas['totalventa'], errors='coerce')

            #2. Se desenrrolla el Array de 'productos' para poder analizar libro por libro vendido con .explode
            df_ventas_desglosado = df_ventas.explode('productos')

            #3. Se agrupan por el nombre del producto y sumamos los ingresos acumulados
            #En el array se guarda el título directo y se agrupa por 'productos'.
            ventas_agrupadas = df_ventas_desglosado.groupby('productos')['totalventa'].sum().reset_index()

            #Se Renombra las columnas finales de la tabla analítica para la interfaz
            ventas_agrupadas = ventas_agrupadas.rename(columns={'productos': 'Libro', 'totalventa': 'Total Ventas ($)'})

            #4. Se ordena de mayor a menor rendimiento de ventas y tomamos el Top 10
            ventas_agrupadas = ventas_agrupadas.sort_values(by='Total Ventas ($)', ascending=False).head(10)

            if not ventas_agrupadas.empty:
                #5. Interfaz visual estructurado con st.columns
                col1, col2 = st.columns([1, 2])

                with col1:
                    #Se obtiene la información del libro más exitoso en la nube
                    libro_top = ventas_agrupadas.iloc[0]['Libro']
                    monto_top = ventas_agrupadas.iloc[0]['Total Ventas ($)']

                    st.metric(label="😲 Libro más Vendido", value=str(libro_top), delta=f"${monto_top:,.2f}")
                    st.write("Visualización analítica en tiempo real basada en los documentos de MongoDB Atlas.")

                with col2:
                    #Se formatea el eje para mostrar la gráfica de barras de Streamlit
                    grafica_data = ventas_agrupadas.set_index('Libro')
                    st.bar_chart(grafica_data, use_container_width=True)
            else:
                st.warning("Los datos de ventas no pudieron procesarse correctamente.")
        else:
            st.error("No se encontraron los campos 'productos' o 'totalventa' en la colección de Ventas.")
    else:
        st.info("Para visualizar el Dashboard, debes de tener documentos cargados en tus colecciones de MongoDB.")

# Pestaña para Ver
with pestanas[1]:
    if lista_datos: 
        df = pd.DataFrame(lista_datos) 
        if '_id' in df.columns: 
            df['_id'] = df['_id'].astype(str)
        
        # Si la columna 'generos' existe, convertimos temporalmente todo a texto plano
        if 'generos' in df.columns:
            df['generos'] = df['generos'].apply(lambda x: ", ".join(map(str, x)) if isinstance(x, list) else str(x))
            
        st.dataframe(df, use_container_width=True) 
    else:
        st.info("No hay registros.")

# Pestaña para Agregar
with pestanas[2]:
    with st.form("formulario_agregar"):
        datos_nuevos = {}
        for campo in campos_por_coleccion.get(nombre_coleccion, ["Nombre"]):
            # Identificamos si el campo debe ser numérico
            if campo in ["Precio", "Stock", "Total"]:
                if campo == "Stock":
                    datos_nuevos[campo.lower()] = st.number_input(campo, min_value=0, step=1)
                else:
                    datos_nuevos[campo.lower()] = st.number_input(campo, min_value=0.0, step=0.01)
            else:
                clave = campo.lower().replace("título", "titulo")
                datos_nuevos[clave] = st.text_input(campo)

        if st.form_submit_button("Guardar"):
            if nombre_coleccion == "Ventas" and "fecha" in datos_nuevos:
                if not datos_nuevos["fecha"]:
                    datos_nuevos["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            #Se inserta el documento en MongoDB Atlas
            coleccion.insert_one(datos_nuevos)
            
            #Se Muestra el mensaje de éxito en la pantalla
            st.success("¡Guardado con éxito con el tipo de dato correcto!")
            
            #Se pone un botón temporal de actualización para que no se borre el mensaje verde solo
            st.info("💡 Haz clic en cualquier otra pestaña o usa el menú lateral")

#Pestaña para Ticket
with pestanas[3]:
    if lista_datos:
        ids = [str(dato['_id']) for dato in lista_datos] #Para que solo me muestro los _id y como están en formato BSON (MongoDB) los convierto a String para que puedan aparecer en mis Lista desplegable
        seleccion_id = st.selectbox("Selecciona un ID", ids) #Una vez hecho lo de arriba, muestro los _id en string
        if st.button("Generar un Ticket"):
            dato_buscado = coleccion.find_one({"_id": ObjectId(seleccion_id)}) #El Formato BSON en string se convierte en BSON para buscar en el Diccionario en MongoDB
            st.subheader("Ticket")
            for campo, valor in dato_buscado.items(): #Para mostrar en orden los campos y valores del Diccionario seleccionado de MongoDB
                if campo != '_id':
                    st.write(f"**{campo.capitalize()}:** {valor}") #Para negrita y capitalize para presentación (ejemplo: precio a Precio)

#Pestaña para Eliminar
with pestanas[4]:
    if lista_datos:
        # Generamos los IDs de forma segura asegurándonos de que existan
        ids = [str(dato['_id']) for dato in lista_datos if '_id' in dato] 
        id_a_borrar = st.selectbox("Selecciona ID para borrar", ids) 
        if st.button("Confirmar Borrado"):
            coleccion.delete_one({"_id": ObjectId(id_a_borrar)}) 
            st.error("Eliminado correctamente.") 
            st.rerun()
    else:
        st.info("No hay registros para eliminar.")

#Ejecutar Servidor Streamlit y app.py
!nohup streamlit run app.py &
!npx localtunnel --port 8501 & curl ipv4.icanhazip.com
