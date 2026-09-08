import pandas as pd
import json

with open('datos/ventas.json', 'r', encoding='utf-8') as archivo:
    contenido= json.load(archivo)


pd.set_option('display.max_columns',None)
ventas= pd.json_normalize(contenido['ventas'])

for columna in ventas.columns:
    print(columna)

data_frame= ventas[['numero_factura', 'fecha', 'hora','linea', 'producto.codigo_producto', 'cantidad.cantidad_vendida','financiero.precio_unitario_usd']]

print(data_frame)

data_frame.to_json('datos/ventas_limpias.json', orient='records', date_format='iso')
