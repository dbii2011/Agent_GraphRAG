import requests

class SNCFClient:

    def __init__(self):
        self.base_url = (
            "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets"
        )

    def get_ponts(self, limit=1):

        url = (
            f"{self.base_url}/liste-des-ponts-route/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()

    def get_quais(self, limit=1):

        url = (
            f"{self.base_url}/liste-des-quais/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()
    def get_chantiers(self, limit=1):

        url = (
            f"{self.base_url}/liste-des-chantiers/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()
    def get_triages(self, limit=1):

        url = (
            f"{self.base_url}/liste-des-triages/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()
    def get_circuit(self, limit=1):

        url = (
            f"{self.base_url}/liste-des-circuits-de-voie/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()
    def get_gares(self, limit=1):

        url = (
            f"{self.base_url}/liste-des-gares/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()
    def get_passages_souterrains(self, limit=1):

        url = (
            f"{self.base_url}/liste-des-passages-souterrains/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()
    def get_gabarit_obstacles_hauts_voyageurs(self, limit=1):

        url = (
            f"{self.base_url}/gabarit-limite-des-obstacles-hauts-voyageurs/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()
    
    def get_lignes_par_region_administrative(self, limit=1):

        url = (
            f"{self.base_url}/lignes-par-region-administrative/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()
    
    def get_lignes_par_statut(self, limit=1):

        url = (
            f"{self.base_url}/lignes-par-statut/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()
        return response.json()
    
    def get_vitesse_maximale_nominale_sur_ligne(self, limit=1):

        url = (
            f"{self.base_url}/vitesse-maximale-nominale-sur-ligne/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()

        return response.json()
    
    def get_lignes_equipees_de_kvb(self, limit=1):

        url = (
            f"{self.base_url}/lignes-equipees-de-kvb/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()
        return response.json()
    
    def get_mode_de_cantonnement_des_lignes(self, limit=1):

        url = (
            f"{self.base_url}/mode-de-cantonnement-des-lignes/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()
        return response.json()
    
    def get_lignes_equipees_de_liaison_radio_sol_train(self, limit=1):

        url = (
            f"{self.base_url}/lignes-equipees-de-liaison-radio-sol-train/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()
        return response.json()
    
    def get_liste_des_passerelles(self, limit=1):

        url = (
            f"{self.base_url}/liste-des-passerelles/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()
        return response.json()
    
    def get_liste_des_passages_a_niveau(self, limit=1):

        url = (
            f"{self.base_url}/liste-des-passages-a-niveau/records"
        )

        response = requests.get(
            url,
            params={"limit": limit},
            timeout=30
        )

        response.raise_for_status()
        return response.json()
    

    

    
    

    
    
    

    
    