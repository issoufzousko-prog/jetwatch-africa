import { API_URL } from '../services/api';

export const AFRICAN_COUNTRIES_ISO: Record<string, string> = {
  "Algerie": "dz",
  "Angola": "ao",
  "Benin": "bj",
  "Botswana": "bw",
  "Burkina Faso": "bf",
  "Burundi": "bi",
  "Cameroun": "cm",
  "Cap-Vert": "cv",
  "Republique Centrafricaine": "cf",
  "Republique centrafricaine": "cf",
  "Tchad": "td",
  "Comores": "km",
  "Congo-Brazzaville": "cg",
  "RD Congo": "cd",
  "Republique Democratique du Congo": "cd",
  "Cote d'Ivoire": "ci",
  "Djibouti": "dj",
  "Egypte": "eg",
  "Guinee equatoriale": "gq",
  "Erythree": "er",
  "Eswatini": "sz",
  "Ethiopie": "et",
  "Gabon": "ga",
  "Gambie": "gm",
  "Ghana": "gh",
  "Guinee": "gn",
  "Guinee-Bissau": "gw",
  "Kenya": "ke",
  "Lesotho": "ls",
  "Liberia": "lr",
  "Libye": "ly",
  "Madagascar": "mg",
  "Malawi": "mw",
  "Mali": "ml",
  "Mauritanie": "mr",
  "Maurice": "mu",
  "Maroc": "ma",
  "Mozambique": "mz",
  "Namibie": "na",
  "Niger": "ne",
  "Nigeria": "ng",
  "Rwanda": "rw",
  "Sao Tome-et-Principe": "st",
  "Senegal": "sn",
  "Seychelles": "sc",
  "Sierra Leone": "sl",
  "Somalie": "so",
  "Afrique du Sud": "za",
  "Soudan du Sud": "ss",
  "Soudan": "sd",
  "Tanzanie": "tz",
  "Togo": "tg",
  "Tunisie": "tn",
  "Ouganda": "ug",
  "Zambie": "zm",
  "Zimbabwe": "zw"
};

export function getFlagUrl(pays: string | null | undefined): string | null {
  if (!pays) return null;
  const normalizedPays = pays.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

  const isoCode = Object.keys(AFRICAN_COUNTRIES_ISO).find(
    k => k.toLowerCase().replace(/[\u0300-\u036f]/g, "") === normalizedPays
  );

  if (isoCode) {
    return `https://flagcdn.com/w40/${AFRICAN_COUNTRIES_ISO[isoCode]}.png`;
  }

  return null;
}

export function getProfileImageUrl(pays: string | null | undefined, photoUrl?: string): string {
  if (photoUrl) {
    return `${API_URL}/proxy-image?url=${encodeURIComponent(photoUrl)}`;
  }
  return getFlagUrl(pays) || `https://ui-avatars.com/api/?name=${encodeURIComponent(pays || "Inconnu")}&background=1e293b&color=fff&rounded=true`;
}
