def get_power_of_set(sets_list, set_name):
    for item in sets_list:
        if item["SET"] == set_name:
            return item["Power_SET"]
    return None  # si no existe

def get_turbines_sets(sets_list, set_name):
    for item in sets_list:
        if item["SET"] == set_name:
            return item["N_WTGs"]


'''# --- Clase SET (como la tienes) ---
    class SET:
        def __init__(self, id, WTGs, utm_x, utm_y, POWER):
            self.id = id
            self.WTGs = WTGs
            self.power_set = round((WTGs) * POWER, 1)
            self.utm_x = utm_x
            self.utm_y = utm_y
        def coord_set(self):
            return (self.utm_x, self.utm_y)
        def resume(self):
            return {
                "SET": self.id,
                "N_WTGs": self.WTGs,
                "Power_SET": self.power_set,
                "UTM_X": self.utm_x,
                "UTM_Y": self.utm_y,
                "WTGs": self.WTGs,
            }'''