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
  }
};

/**
 * Crisp, scalable SVG Flag component with accessible aria-label
 */
export function CountryFlag({ code, size = 'md', className = '' }) {
  const meta = COUNTRY_METADATA[code?.toUpperCase()] || {
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
    switch (code?.toUpperCase()) {
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
  return COUNTRY_METADATA[code?.toUpperCase()]?.name || 'International';
}

export function getCountryFlagEmoji(code) {
  return COUNTRY_METADATA[code?.toUpperCase()]?.emoji || '🏁';
}
