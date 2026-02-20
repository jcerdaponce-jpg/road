


def power_range(AT_V,POWER):

    if AT_V == 66 or AT_V == 69:
        power_per_circuit = 109
        circuit_number = POWER / power_per_circuit
    if AT_V == 110 or AT_V == 132:
        power_per_circuit = 142.5
        circuit_number = POWER / power_per_circuit
    if AT_V == 220 or AT_V == 230:
        power_per_circuit = 380
        circuit_number = POWER / power_per_circuit


    return circuit_number

def circuit_length(POWER,AT_V,ohl_length):

    circuit_number=power_range(AT_V,POWER)

    glosa_1 = f'ohl_simple_circuito_{AT_V}_kV'
    glosa_2 = f'ohl_doble_circuito_{AT_V}_kV'

    if circuit_number <= 1:
        # 1 circuito simple
        one_circuit_length = ohl_length * 1
        two_circuit_length = 0.0
        HV_circuit = 1
    elif 1 < circuit_number <= 2:
        # 1 circuito doble
        one_circuit_length = 0.0
        two_circuit_length= ohl_length * 1
        HV_circuit = 2
    elif 2 < circuit_number <= 3:
        # 1 simple + 1 doble
        one_circuit_length = ohl_length * 1
        two_circuit_length= ohl_length * 1
        HV_circuit = 3
    elif 3 <circuit_number <= 4:
        # 2 dobles
        one_circuit_length = 0.0
        two_circuit_length = ohl_length * 2
        HV_circuit = 4
    elif 4 < circuit_number <= 5:
        # 1 simple + 2 dobles
        one_circuit_length = ohl_length* 1
        two_circuit_length= ohl_length * 2
        HV_circuit = 5
    else:
        # Fuera de los rangos definidos (avisa o ajusta según criterio)
        # Aquí dejo todo a 0 y podrías loguear/avisar:
        print(f"[WARN] h={circuit_number} fuera de los rangos manejados (<=1 ... <=5). Ajusta la lógica si es necesario.")

    lista_record = {
        'LEVEL VOLTAGE [kv]': AT_V,
        'Power transfer [MVA]': POWER,
        f'{glosa_1} [km]': round(one_circuit_length / 1000, 3),
        f'{glosa_2} [km]': round(two_circuit_length / 1000, 3),
        'Number circuits': HV_circuit,
    }


    return lista_record



