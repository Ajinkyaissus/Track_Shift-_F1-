import React from 'react';

// ISO 3166-1 Alpha-2 to Country Metadata & SVG Flag paths
export const COUNTRY_METADATA = {
  IT: {
    code: 'IT',
    name: 'Italy',
    demonym: 'Italian',
    emoji: '🇮🇹',
    colors: ['#009246', '#FFFFFF', '#CE2B37']
  },
  BE: {
    code: 'BE',
    name: 'Belgium',
    demonym: 'Belgian',
    emoji: '🇧🇪',
    colors: ['#000000', '#FFD100', '#EF3340']
  },
  GB: {
    code: 'GB',
    name: 'United Kingdom',
    demonym: 'British',
    emoji: '🇬🇧',
    colors: ['#012169', '#C8102E', '#FFFFFF']
  },
  MC: {
    code: 'MC',
    name: 'Monaco',
    demonym: 'Monegasque',
    emoji: '🇲🇨',
    colors: ['#CE1126', '#FFFFFF']
  },
  HU: {
    code: 'HU',
    name: 'Hungary',
    demonym: 'Hungarian',
    emoji: '🇭🇺',
    colors: ['#CE2939', '#FFFFFF', '#477050']
  },
  BH: {
    code: 'BH',
    name: 'Bahrain',
    demonym: 'Bahraini',
    emoji: '🇧🇭',
    colors: ['#CE1126', '#FFFFFF']
  },
  SA: {
    code: 'SA',
    name: 'Saudi Arabia',
    demonym: 'Saudi',
    emoji: '🇸🇦',
    colors: ['#006C35', '#FFFFFF']
  },
  AE: {
    code: 'AE',
    name: 'United Arab Emirates',
    demonym: 'Emirati',
    emoji: '🇦🇪',
    colors: ['#00732F', '#FFFFFF', '#000000', '#FF0000']
  },
  US: {
    code: 'US',
    name: 'United States',
    demonym: 'American',
    emoji: '🇺🇸',
    colors: ['#B22234', '#FFFFFF', '#3C3B6E']
  },
  BR: {
    code: 'BR',
    name: 'Brazil',
    demonym: 'Brazilian',
    emoji: '🇧🇷',
    colors: ['#009739', '#FEDD00', '#012169']
  },
  JP: {
    code: 'JP',
    name: 'Japan',
    demonym: 'Japanese',
    emoji: '🇯🇵',
    colors: ['#FFFFFF', '#BC002D']
  },
  SG: {
    code: 'SG',
    name: 'Singapore',
    demonym: 'Singaporean',
    emoji: '🇸🇬',
    colors: ['#ED2939', '#FFFFFF']
  },
  AU: {
    code: 'AU',
    name: 'Australia',
    demonym: 'Australian',
    emoji: '🇦🇺',
    colors: ['#012169', '#E4002B', '#FFFFFF']
  },
  ES: {
    code: 'ES',
    name: 'Spain',
    demonym: 'Spanish',
    emoji: '🇪🇸',
    colors: ['#AA151B', '#F1BF00', '#AA151B']
  },
  NL: {
    code: 'NL',
    name: 'Netherlands',
    demonym: 'Dutch',
    emoji: '🇳🇱',
    colors: ['#AE1C28', '#FFFFFF', '#21468B']
  },
  AT: {
    code: 'AT',
    name: 'Austria',
    demonym: 'Austrian',
    emoji: '🇦🇹',
    colors: ['#ED2939', '#FFFFFF', '#ED2939']
  },
  CA: {
    code: 'CA',
    name: 'Canada',
    demonym: 'Canadian',
    emoji: '🇨🇦',
    colors: ['#FF0000', '#FFFFFF']
  },
  MX: {
    code: 'MX',
    name: 'Mexico',
    demonym: 'Mexican',
    emoji: '🇲🇽',
    colors: ['#006847', '#FFFFFF', '#CE1126']
  },
  AZ: {
    code: 'AZ',
    name: 'Azerbaijan',
    demonym: 'Azerbaijani',
    emoji: '🇦🇿',
    colors: ['#0092BC', '#E4002B', '#009739']
  },
  QA: {
    code: 'QA',
    name: 'Qatar',
    demonym: 'Qatari',
    emoji: '🇶🇦',
    colors: ['#8D1B3D', '#FFFFFF']
  },
  CN: {
    code: 'CN',
    name: 'China',
    demonym: 'Chinese',
    emoji: '🇨🇳',
    colors: ['#EE1C25', '#FFFF00']
  },
  FR: {
    code: 'FR',
    name: 'France',
    demonym: 'French',
    emoji: '🇫🇷',
    colors: ['#002654', '#FFFFFF', '#ED2939']
  },
  DE: {
    code: 'DE',
    name: 'Germany',
    demonym: 'German',
    emoji: '🇩🇪',
    colors: ['#000000', '#DD0000', '#FFCE00']
  },
  FI: {
    code: 'FI',
    name: 'Finland',
    demonym: 'Finnish',
    emoji: '🇫🇮',
    colors: ['#FFFFFF', '#002F6C']
  },
  DK: {
    code: 'DK',
    name: 'Denmark',
    demonym: 'Danish',
    emoji: '🇩🇰',
    colors: ['#C8102E', '#FFFFFF']
  },
  TH: {
    code: 'TH',
    name: 'Thailand',
    demonym: 'Thai',
    emoji: '🇹🇭',
    colors: ['#A51931', '#F4F5F8', '#2D2A4A']
  },
  NZ: {
    code: 'NZ',
    name: 'New Zealand',
    demonym: 'New Zealander',
    emoji: '🇳🇿',
    colors: ['#00247D', '#CC142B', '#FFFFFF']
  },
  AR: {
    code: 'AR',
    name: 'Argentina',
    demonym: 'Argentine',
    emoji: '🇦🇷',
    colors: ['#74ACDF', '#FFFFFF', '#F6B40E']
  },
  CH: {
    code: 'CH',
    name: 'Switzerland',
    demonym: 'Swiss',
    emoji: '🇨🇭',
    colors: ['#FF0000', '#FFFFFF']
  },
  IE: {
    code: 'IE',
    name: 'Ireland',
    demonym: 'Irish',
    emoji: '🇮🇪',
    colors: ['#169B62', '#FFFFFF', '#FF883E']
  },
  PT: {
    code: 'PT',
    name: 'Portugal',
    demonym: 'Portuguese',
    emoji: '🇵🇹',
    colors: ['#046A38', '#DA291C', '#FFD100']
  },
  PL: {
    code: 'PL',
    name: 'Poland',
    demonym: 'Polish',
    emoji: '🇵🇱',
    colors: ['#FFFFFF', '#DC143C']
  },
  SE: {
    code: 'SE',
    name: 'Sweden',
    demonym: 'Swedish',
    emoji: '🇸🇪',
    colors: ['#005293', '#FECB00']
  },
  ZA: {
    code: 'ZA',
    name: 'South Africa',
    demonym: 'South African',
    emoji: '🇿🇦',
    colors: ['#007749', '#001489', '#E03C31', '#FFB81C', '#000000', '#FFFFFF']
  },
  MY: {
    code: 'MY',
    name: 'Malaysia',
    demonym: 'Malaysian',
    emoji: '🇲🇾',
    colors: ['#CC0000', '#FFFFFF', '#000066', '#FFCC00']
  },
  TR: {
    code: 'TR',
    name: 'Turkey',
    demonym: 'Turkish',
    emoji: '🇹🇷',
    colors: ['#E30A17', '#FFFFFF']
  }
};

// Aliases lookup table: supports IOC/FIA 3-letter codes, country names, and demonyms
const COUNTRY_ALIASES = {
  // 3-letter IOC / FIA / ISO Alpha-3 codes
  ITA: 'IT',
  BEL: 'BE',
  GBR: 'GB',
  UK: 'GB',
  ENG: 'GB',
  SCO: 'GB',
  WAL: 'GB',
  MON: 'MC',
  MCO: 'MC',
  HUN: 'HU',
  BHR: 'BH',
  SAU: 'SA',
  KSA: 'SA',
  UAE: 'AE',
  ARE: 'AE',
  USA: 'US',
  BRA: 'BR',
  JPN: 'JP',
  SGP: 'SG',
  SIN: 'SG',
  AUS: 'AU',
  ESP: 'ES',
  SPA: 'ES',
  NED: 'NL',
  NLD: 'NL',
  AUT: 'AT',
  CAN: 'CA',
  MEX: 'MX',
  AZE: 'AZ',
  QAT: 'QA',
  CHN: 'CN',
  FRA: 'FR',
  GER: 'DE',
  DEU: 'DE',
  FIN: 'FI',
  DEN: 'DK',
  DNK: 'DK',
  THA: 'TH',
  NZL: 'NZ',
  ARG: 'AR',
  SUI: 'CH',
  CHE: 'CH',
  IRL: 'IE',
  POR: 'PT',
  PRT: 'PT',
  POL: 'PL',
  SWE: 'SE',
  RSA: 'ZA',
  ZAF: 'ZA',
  MAS: 'MY',
  MYS: 'MY',
  TUR: 'TR',

  // Full country names
  ITALY: 'IT',
  BELGIUM: 'BE',
  'UNITED KINGDOM': 'GB',
  'GREAT BRITAIN': 'GB',
  ENGLAND: 'GB',
  MONACO: 'MC',
  HUNGARY: 'HU',
  BAHRAIN: 'BH',
  'SAUDI ARABIA': 'SA',
  'UNITED ARAB EMIRATES': 'AE',
  'UNITED STATES': 'US',
  'UNITED STATES OF AMERICA': 'US',
  BRAZIL: 'BR',
  JAPAN: 'JP',
  SINGAPORE: 'SG',
  AUSTRALIA: 'AU',
  SPAIN: 'ES',
  NETHERLANDS: 'NL',
  AUSTRIA: 'AT',
  CANADA: 'CA',
  MEXICO: 'MX',
  AZERBAIJAN: 'AZ',
  QATAR: 'QA',
  CHINA: 'CN',
  FRANCE: 'FR',
  GERMANY: 'DE',
  FINLAND: 'FI',
  DENMARK: 'DK',
  THAILAND: 'TH',
  'NEW ZEALAND': 'NZ',
  ARGENTINA: 'AR',
  SWITZERLAND: 'CH',
  IRELAND: 'IE',
  PORTUGAL: 'PT',
  POLAND: 'PL',
  SWEDEN: 'SE',
  'SOUTH AFRICA': 'ZA',
  MALAYSIA: 'MY',
  TURKEY: 'TR',

  // Demonyms / Nationalities
  ITALIAN: 'IT',
  BELGIAN: 'BE',
  BRITISH: 'GB',
  ENGLISH: 'GB',
  SCOTTISH: 'GB',
  MONEGASQUE: 'MC',
  HUNGARIAN: 'HU',
  BAHRAINI: 'BH',
  SAUDI: 'SA',
  EMIRATI: 'AE',
  AMERICAN: 'US',
  BRAZILIAN: 'BR',
  JAPANESE: 'JP',
  SINGAPOREAN: 'SG',
  AUSTRALIAN: 'AU',
  SPANISH: 'ES',
  DUTCH: 'NL',
  AUSTRIAN: 'AT',
  CANADIAN: 'CA',
  MEXICAN: 'MX',
  AZERBAIJANI: 'AZ',
  QATARI: 'QA',
  CHINESE: 'CN',
  FRENCH: 'FR',
  GERMAN: 'DE',
  FINNISH: 'FI',
  DANISH: 'DK',
  THAI: 'TH',
  'NEW ZEALANDER': 'NZ',
  KIWI: 'NZ',
  ARGENTINE: 'AR',
  ARGENTINIAN: 'AR',
  SWISS: 'CH',
  IRISH: 'IE',
  PORTUGUESE: 'PT',
  POLISH: 'PL',
  SWEDISH: 'SE',
  'SOUTH AFRICAN': 'ZA',
  MALAYSIAN: 'MY',
  TURKISH: 'TR'
};

/**
 * Normalizes any country representation (2-letter code, 3-letter code, full name, demonym)
 * into a valid 2-letter uppercase ISO code.
 */
export function normalizeCountryCode(input) {
  if (!input || typeof input !== 'string') return null;
  const clean = input.trim().toUpperCase();
  if (COUNTRY_METADATA[clean]) return clean;
  if (COUNTRY_ALIASES[clean]) return COUNTRY_ALIASES[clean];
  return clean;
}

/**
 * Crisp, scalable SVG Flag component with accessible aria-label
 */
export function CountryFlag({ code, size = 'md', className = '' }) {
  const normCode = normalizeCountryCode(code);
  const meta = COUNTRY_METADATA[normCode] || {
    name: 'International',
    emoji: '🏁'
  };

  const sizeClasses = {
    sm: 'w-5 h-3.5 text-xs',
    md: 'w-7 h-5 text-sm',
    lg: 'w-10 h-7 text-base',
    xl: 'w-14 h-10 text-xl'
  };

  // High quality SVG renderers for crisp motorsport broadcast look
  const renderFlagSVG = () => {
    switch (normCode) {
      case 'IT':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="10" height="20" fill="#009246" />
            <rect x="10" width="10" height="20" fill="#FFFFFF" />
            <rect x="20" width="10" height="20" fill="#CE2B37" />
          </svg>
        );
      case 'BE':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="10" height="20" fill="#000000" />
            <rect x="10" width="10" height="20" fill="#FFD100" />
            <rect x="20" width="10" height="20" fill="#EF3340" />
          </svg>
        );
      case 'GB':
        return (
          <svg viewBox="0 0 60 30" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <clipPath id="gb-clip"><rect width="60" height="30" /></clipPath>
            <g clipPath="url(#gb-clip)">
              <rect width="60" height="30" fill="#012169" />
              <path d="M0,0 L60,30 M60,0 L0,30" stroke="#FFFFFF" strokeWidth="6" />
              <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" strokeWidth="2" />
              <path d="M30,0 v30 M0,15 h60" stroke="#FFFFFF" strokeWidth="10" />
              <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
            </g>
          </svg>
        );
      case 'MC':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="10" fill="#CE1126" />
            <rect y="10" width="30" height="10" fill="#FFFFFF" />
          </svg>
        );
      case 'HU':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="6.66" fill="#CE2939" />
            <rect y="6.66" width="30" height="6.66" fill="#FFFFFF" />
            <rect y="13.33" width="30" height="6.67" fill="#477050" />
          </svg>
        );
      case 'BH':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#CE1126" />
            <polygon points="0,0 8,0 11,2 8,4 11,6 8,8 11,10 8,12 11,14 8,16 11,18 8,20 0,20" fill="#FFFFFF" />
          </svg>
        );
      case 'SA':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#006C35" />
            <rect x="7" y="13" width="16" height="2" fill="#FFFFFF" rx="1" />
            <text x="15" y="9" fill="#FFFFFF" fontSize="6" textAnchor="middle" fontWeight="bold">SA</text>
          </svg>
        );
      case 'AE':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="6.66" fill="#00732F" />
            <rect y="6.66" width="30" height="6.66" fill="#FFFFFF" />
            <rect y="13.33" width="30" height="6.67" fill="#000000" />
            <rect width="8" height="20" fill="#FF0000" />
          </svg>
        );
      case 'US':
        return (
          <svg viewBox="0 0 38 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="38" height="20" fill="#B22234" />
            <rect y="1.54" width="38" height="1.54" fill="#FFFFFF" />
            <rect y="4.62" width="38" height="1.54" fill="#FFFFFF" />
            <rect y="7.7" width="38" height="1.54" fill="#FFFFFF" />
            <rect y="10.77" width="38" height="1.54" fill="#FFFFFF" />
            <rect y="13.85" width="38" height="1.54" fill="#FFFFFF" />
            <rect y="16.92" width="38" height="1.54" fill="#FFFFFF" />
            <rect width="15.2" height="10.77" fill="#3C3B6E" />
          </svg>
        );
      case 'BR':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#009739" />
            <polygon points="15,2 27,10 15,18 3,10" fill="#FEDD00" />
            <circle cx="15" cy="10" r="4.2" fill="#012169" />
          </svg>
        );
      case 'JP':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#FFFFFF" />
            <circle cx="15" cy="10" r="6" fill="#BC002D" />
          </svg>
        );
      case 'SG':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="10" fill="#ED2939" />
            <rect y="10" width="30" height="10" fill="#FFFFFF" />
            <circle cx="7" cy="5" r="3.2" fill="#FFFFFF" />
            <circle cx="8" cy="5" r="3.2" fill="#ED2939" />
          </svg>
        );
      case 'AU':
        return (
          <svg viewBox="0 0 40 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="40" height="20" fill="#012169" />
            <g transform="scale(0.5)">
              <rect width="40" height="20" fill="#012169" />
              <path d="M0,0 L40,20 M40,0 L0,20" stroke="#FFFFFF" strokeWidth="4" />
              <path d="M0,0 L40,20 M40,0 L0,20" stroke="#E4002B" strokeWidth="1.5" />
              <path d="M20,0 v20 M0,10 h40" stroke="#FFFFFF" strokeWidth="6" />
              <path d="M20,0 v20 M0,10 h40" stroke="#E4002B" strokeWidth="4" />
            </g>
            <circle cx="10" cy="15" r="2" fill="#FFFFFF" />
            <circle cx="30" cy="5" r="1.2" fill="#FFFFFF" />
            <circle cx="34" cy="8" r="1.2" fill="#FFFFFF" />
            <circle cx="30" cy="12" r="1.2" fill="#FFFFFF" />
            <circle cx="26" cy="9" r="1.2" fill="#FFFFFF" />
          </svg>
        );
      case 'ES':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="5" fill="#AA151B" />
            <rect y="5" width="30" height="10" fill="#F1BF00" />
            <rect y="15" width="30" height="5" fill="#AA151B" />
            <circle cx="8.5" cy="10" r="2.2" fill="#AA151B" opacity="0.8" />
          </svg>
        );
      case 'NL':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="6.66" fill="#AE1C28" />
            <rect y="6.66" width="30" height="6.66" fill="#FFFFFF" />
            <rect y="13.33" width="30" height="6.67" fill="#21468B" />
          </svg>
        );
      case 'AT':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="6.66" fill="#ED2939" />
            <rect y="6.66" width="30" height="6.66" fill="#FFFFFF" />
            <rect y="13.33" width="30" height="6.67" fill="#ED2939" />
          </svg>
        );
      case 'CA':
        return (
          <svg viewBox="0 0 40 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="10" height="20" fill="#FF0000" />
            <rect x="10" width="20" height="20" fill="#FFFFFF" />
            <rect x="30" width="10" height="20" fill="#FF0000" />
            <polygon points="20,4 21.5,8 24,7 23,10 26,11 25,13 21,13 20.5,16 19.5,16 19,13 15,13 14,11 17,10 16,7 18.5,8" fill="#FF0000" />
          </svg>
        );
      case 'MX':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="10" height="20" fill="#006847" />
            <rect x="10" width="10" height="20" fill="#FFFFFF" />
            <rect x="20" width="10" height="20" fill="#CE1126" />
            <circle cx="15" cy="10" r="2" fill="#7B5B34" />
          </svg>
        );
      case 'AZ':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="6.66" fill="#0092BC" />
            <rect y="6.66" width="30" height="6.66" fill="#E4002B" />
            <rect y="13.33" width="30" height="6.67" fill="#009739" />
            <circle cx="14" cy="10" r="2.2" fill="#FFFFFF" />
            <circle cx="14.6" cy="10" r="1.8" fill="#E4002B" />
            <polygon points="17,9 17.6,10 17,11 16.4,10" fill="#FFFFFF" />
          </svg>
        );
      case 'QA':
        return (
          <svg viewBox="0 0 38 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="38" height="20" fill="#8D1B3D" />
            <polygon points="0,0 10,0 13,1.1 10,2.2 13,3.3 10,4.4 13,5.5 10,6.6 13,7.7 10,8.8 13,10 10,11.1 13,12.2 10,13.3 13,14.4 10,15.5 13,16.6 10,17.7 13,18.8 10,20 0,20" fill="#FFFFFF" />
          </svg>
        );
      case 'CN':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#EE1C25" />
            <polygon points="5,2 6,4.5 8.5,4.5 6.5,6 7.5,8.5 5,7 2.5,8.5 3.5,6 1.5,4.5 4,4.5" fill="#FFFF00" />
            <circle cx="10" cy="3" r="0.8" fill="#FFFF00" />
            <circle cx="12" cy="5" r="0.8" fill="#FFFF00" />
            <circle cx="12" cy="8" r="0.8" fill="#FFFF00" />
            <circle cx="10" cy="10" r="0.8" fill="#FFFF00" />
          </svg>
        );
      case 'FR':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="10" height="20" fill="#002654" />
            <rect x="10" width="10" height="20" fill="#FFFFFF" />
            <rect x="20" width="10" height="20" fill="#ED2939" />
          </svg>
        );
      case 'DE':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="6.66" fill="#000000" />
            <rect y="6.66" width="30" height="6.66" fill="#DD0000" />
            <rect y="13.33" width="30" height="6.67" fill="#FFCE00" />
          </svg>
        );
      case 'FI':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#FFFFFF" />
            <rect x="8" width="5" height="20" fill="#002F6C" />
            <rect y="7.5" width="30" height="5" fill="#002F6C" />
          </svg>
        );
      case 'DK':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#C8102E" />
            <rect x="8.5" width="4" height="20" fill="#FFFFFF" />
            <rect y="8" width="30" height="4" fill="#FFFFFF" />
          </svg>
        );
      case 'TH':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="3.33" fill="#A51931" />
            <rect y="3.33" width="30" height="3.33" fill="#F4F5F8" />
            <rect y="6.66" width="30" height="6.68" fill="#2D2A4A" />
            <rect y="13.34" width="30" height="3.33" fill="#F4F5F8" />
            <rect y="16.67" width="30" height="3.33" fill="#A51931" />
          </svg>
        );
      case 'NZ':
        return (
          <svg viewBox="0 0 40 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="40" height="20" fill="#00247D" />
            <g transform="scale(0.5)">
              <rect width="40" height="20" fill="#00247D" />
              <path d="M0,0 L40,20 M40,0 L0,20" stroke="#FFFFFF" strokeWidth="4" />
              <path d="M0,0 L40,20 M40,0 L0,20" stroke="#CC142B" strokeWidth="1.5" />
              <path d="M20,0 v20 M0,10 h40" stroke="#FFFFFF" strokeWidth="6" />
              <path d="M20,0 v20 M0,10 h40" stroke="#CC142B" strokeWidth="4" />
            </g>
            <polygon points="30,4 30.6,5.5 32,5.5 31,6.5 31.5,8 30,7 28.5,8 29,6.5 28,5.5 29.4,5.5" fill="#CC142B" stroke="#FFFFFF" strokeWidth="0.4" />
            <polygon points="35,8 35.5,9.2 36.8,9.2 35.8,10 36.2,11.2 35,10.5 33.8,11.2 34.2,10 33.2,9.2 34.5,9.2" fill="#CC142B" stroke="#FFFFFF" strokeWidth="0.4" />
            <polygon points="30,14 30.6,15.5 32,15.5 31,16.5 31.5,18 30,17 28.5,18 29,16.5 28,15.5 29.4,15.5" fill="#CC142B" stroke="#FFFFFF" strokeWidth="0.4" />
            <polygon points="25,9 25.5,10.2 26.8,10.2 25.8,11 26.2,12.2 25,11.5 23.8,12.2 24.2,11 23.2,10.2 24.5,10.2" fill="#CC142B" stroke="#FFFFFF" strokeWidth="0.4" />
          </svg>
        );
      case 'AR':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="6.66" fill="#74ACDF" />
            <rect y="6.66" width="30" height="6.66" fill="#FFFFFF" />
            <rect y="13.33" width="30" height="6.67" fill="#74ACDF" />
            <circle cx="15" cy="10" r="2" fill="#F6B40E" />
          </svg>
        );
      case 'CH':
        return (
          <svg viewBox="0 0 20 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="20" height="20" fill="#FF0000" />
            <rect x="8" y="4" width="4" height="12" fill="#FFFFFF" />
            <rect x="4" y="8" width="12" height="4" fill="#FFFFFF" />
          </svg>
        );
      case 'IE':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="10" height="20" fill="#169B62" />
            <rect x="10" width="10" height="20" fill="#FFFFFF" />
            <rect x="20" width="10" height="20" fill="#FF883E" />
          </svg>
        );
      case 'PT':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="12" height="20" fill="#046A38" />
            <rect x="12" width="18" height="20" fill="#DA291C" />
            <circle cx="12" cy="10" r="3" fill="#FFD100" />
          </svg>
        );
      case 'PL':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="10" fill="#FFFFFF" />
            <rect y="10" width="30" height="10" fill="#DC143C" />
          </svg>
        );
      case 'SE':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#005293" />
            <rect x="9" width="4" height="20" fill="#FECB00" />
            <rect y="8" width="30" height="4" fill="#FECB00" />
          </svg>
        );
      case 'ZA':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="10" fill="#E03C31" />
            <rect y="10" width="30" height="10" fill="#001489" />
            <polygon points="0,0 12,10 0,20" fill="#000000" />
            <polygon points="0,0 15,10 0,20 0,16 9,10 0,4" fill="#FFB81C" />
            <polygon points="0,3 10.5,10 0,17" fill="#000000" />
            <path d="M0,7.5 L12,7.5 L18,10 L30,10 L30,10 L18,10 L12,12.5 L0,12.5" stroke="#007749" strokeWidth="4" />
          </svg>
        );
      case 'MY':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#FFFFFF" />
            <rect y="0" width="30" height="1.43" fill="#CC0000" />
            <rect y="2.86" width="30" height="1.43" fill="#CC0000" />
            <rect y="5.71" width="30" height="1.43" fill="#CC0000" />
            <rect y="8.57" width="30" height="1.43" fill="#CC0000" />
            <rect y="11.43" width="30" height="1.43" fill="#CC0000" />
            <rect y="14.29" width="30" height="1.43" fill="#CC0000" />
            <rect y="17.14" width="30" height="1.43" fill="#CC0000" />
            <rect width="15" height="10" fill="#000066" />
            <circle cx="6.5" cy="5" r="3" fill="#FFCC00" />
            <circle cx="7.5" cy="5" r="2.5" fill="#000066" />
            <polygon points="10,5 11,4 12,5 11,6" fill="#FFCC00" />
          </svg>
        );
      case 'TR':
        return (
          <svg viewBox="0 0 30 20" className="flag-svg" role="img" aria-label={`Flag of ${meta.name}`}>
            <rect width="30" height="20" fill="#E30A17" />
            <circle cx="11" cy="10" r="5" fill="#FFFFFF" />
            <circle cx="12.5" cy="10" r="4" fill="#E30A17" />
            <polygon points="17,10 18.5,8.8 17.8,10.8 19.5,10.2 18,11.5" fill="#FFFFFF" />
          </svg>
        );
      default:
        return <span className="flag-emoji">{meta.emoji}</span>;
    }
  };

  return (
    <div 
      className={`country-flag-badge ${sizeClasses[size] || sizeClasses.md} ${className}`}
      title={meta.name}
      aria-label={`Flag of ${meta.name}`}
    >
      {renderFlagSVG()}
    </div>
  );
}

export function getCountryName(code) {
  const normCode = normalizeCountryCode(code);
  return COUNTRY_METADATA[normCode]?.name || 'International';
}

export function getCountryFlagEmoji(code) {
  const normCode = normalizeCountryCode(code);
  return COUNTRY_METADATA[normCode]?.emoji || '🏁';
}
