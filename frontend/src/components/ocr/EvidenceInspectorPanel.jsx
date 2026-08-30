import React, { useState } from 'react';
import { Eye, Layers, FileText, ChevronDown, ChevronUp, Info } from 'lucide-react';
import { getGroundedExplanation } from '../../services/api';

const REQUIREMENTS = [
  {
    id: 'MRP',
    name: 'Maximum Retail Price (MRP)',
    field: 'MRP',
    ruleId: 'MRP_DECLARATION_PRESENCE',
    desc: 'The Maximum Retail Price (MRP) must be clearly declared on the package, inclusive of all taxes.',
  },
  {
    id: 'NET_QUANTITY',
    name: 'Net Quantity',
    field: 'NET_QUANTITY',
    ruleId: 'NET_QUANTITY_PRESENCE',
    desc: 'The net quantity of the commodity contained in the package must be declared in terms of standard units of weight, measure, or number.',
  },
  {
    id: 'COMMON_GENERIC_NAME',
    name: 'Generic Commodity Name',
    field: 'COMMON_GENERIC_NAME',
    ruleId: 'COMMON_GENERIC_NAME_DECLARATION_PRESENCE',
    desc: 'The common or generic name of the commodity contained in the package must be declared.',
  },
  {
    id: 'COUNTRY_OF_ORIGIN',
    name: 'Country of Origin',
    field: 'COUNTRY_OF_ORIGIN',
    ruleId: 'COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE',
    desc: 'For packages containing imported commodities, the country of origin or manufacture must be clearly declared.',
  },
  {
    id: 'MONTH_YEAR_MFG_PKD_IMPORT',
    name: 'Month & Year of Manufacture',
    field: 'MONTH_YEAR_MFG_PKD_IMPORT',
    ruleId: 'MONTH_YEAR_DECLARATION_PRESENCE',
    desc: 'The month and year in which the commodity is manufactured, pre-packed, or imported must be declared.',
  },
  {
    id: 'MANUFACTURER_PACKER_IMPORTER_DETAILS',
    name: 'Business Declaration',
    field: 'MANUFACTURER_PACKER_IMPORTER_DETAILS',
    ruleId: 'MANUFACTURER_PACKER_DECLARATION_PRESENCE',
    desc: 'The declared business role, entity name, and address must be reviewed without converting one role into another.',
  },
  {
    id: 'CONSUMER_CARE_DETAILS',
    name: 'Consumer Care Details',
    field: 'CONSUMER_CARE_DETAILS',
    ruleId: 'CONSUMER_CARE_DECLARATION_PRESENCE',
    desc: 'The name, address, telephone number, and email address of the person or office that can be contacted in case of consumer complaints must be declared.',
  },
  {
    id: 'UNIT_SALE_PRICE',
    name: 'Unit Sale Price',
    field: 'UNIT_SALE_PRICE',
    ruleId: 'UNIT_SALE_PRICE_DECLARATION_PRESENCE',
    desc: 'The unit sale price (e.g., price per gram, ml, or item) must be declared on the package where applicable.',
  }
];

const FOOD_REQUIREMENTS = [
  {
    id: 'FSSAI_INGREDIENTS',
    name: 'Ingredients Declaration',
    field: 'FSSAI_INGREDIENTS',
    ruleId: 'FSSAI_INGREDIENTS_DECLARATION',
    desc: 'FSSAI Regulation 5(1)(a) requires every packaged food to declare a complete list of ingredients in descending order of weight/volume.'
  },
  {
    id: 'FSSAI_VEG_NONVEG',
    name: 'Veg / Non-Veg Symbol',
    field: 'FSSAI_VEG_NONVEG',
    ruleId: 'FSSAI_VEG_NONVEG_SYMBOL',
    desc: 'FSSAI Regulation 5(4)(g) mandates a green circle in square (Veg) or brown triangle in square (Non-Veg) declaration.'
  },
  {
    id: 'FSSAI_LICENCE',
    name: 'FSSAI Licence / Registration',
    field: 'FSSAI_LICENCE',
    ruleId: 'FSSAI_LICENCE_PRESENCE',
    desc: 'FSSAI Regulation 5(1)(d) mandates the display of the FSSAI logo and the 14-digit licence/registration number on the label.'
  },
  {
    id: 'FSSAI_ALLERGENS',
    name: 'Allergen Information',
    field: 'FSSAI_ALLERGENS',
    ruleId: 'FSSAI_ALLERGEN_DECLARATION',
    desc: 'FSSAI Regulation 5(1)(c) requires clear declaration of ingredients causing allergies (such as wheat, milk, soy, nuts).'
  },
  {
    id: 'FSSAI_NUTRITION',
    name: 'Nutritional Information',
    field: 'FSSAI_NUTRITION',
    ruleId: 'FSSAI_NUTRITIONAL_INFO',
    desc: 'FSSAI Regulation 5(1)(b) requires nutritional facts per 100g/100ml or per serving (Energy, Carbohydrate, Protein, Fats).'
  }
];

const VISUAL_RULE_TITLES = {
  RULE_7_MINIMUM_NUMERAL_HEIGHT: 'Rule 7: Minimum Numeral & Font Height',
  RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE: 'Rule 8: Surrounding Space Clearance',
  RULE_8_PRINCIPAL_DISPLAY_PANEL_PLACEMENT: 'Rule 8: Principal Display Panel Placement',
  RULE_9_COLOUR_CONTRAST: 'Rule 9: Background Colour Contrast',
  RULE_9_DECLARATION_LEGIBILITY: 'Rule 9: Declaration Legibility',
  RULE_9_RELATIVE_PROMINENCE: 'Rule 9: Relative Prominence',
};

const getFriendlyVisualStatus = (visualRule) => {
  if (visualRule.status === 'NEEDS_RECAPTURE') return 'Take Another Photograph';
  if (visualRule.status === 'OBSERVATION_CLEAR' || visualRule.status === 'PASS') return 'Compliant';
  if (visualRule.status === 'FAIL') return 'Non-compliant';
  if (visualRule.status === 'REVIEW_REQUIRED') return 'Inspector Verification Required';
  if (visualRule.status === 'NOT_APPLICABLE') return 'Not Applicable';
  if (visualRule.status !== 'NOT_EVALUABLE') return 'Needs Officer Review';
  if (visualRule.rule_id?.includes('MINIMUM_NUMERAL_HEIGHT')) return 'Calibrated Measurement Required';
  if (visualRule.rule_id?.includes('PRINCIPAL_DISPLAY_PANEL')) return 'Physical Verification Required';
  if (visualRule.rule_id?.includes('COLOUR_CONTRAST')) return 'Controlled-Lighting Verification Required';
  return 'Not Evaluable From Image';
};

const getVisualStatusClass = (status) => {
  if (status === 'Compliant') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (status === 'Non-compliant') return 'bg-rose-50 text-rose-700 border-rose-200';
  if (status === 'Not Applicable') return 'bg-slate-100 text-slate-700 border-slate-200';
  return 'bg-amber-50 text-amber-700 border-amber-200';
};

const getVisualPresentationReason = (reason) => String(reason || '')
  .replace('Machine OCR confidence and blur metrics', 'Image readability indicators')
  .replace('engineering heuristic', 'comparative presentation indicator')
  .replace('uncalibrated camera RGB values', 'uncalibrated image colour values');

export const PackagePresentationChecks = ({ visualRuleEvaluations = [] }) => {
  const [isOpen, setIsOpen] = useState(false);
  if (visualRuleEvaluations.length === 0) return null;

  return (
    <section id="package-presentation-checks" className="portal-card overflow-hidden">
      <button
        type="button"
        className="flex min-h-16 w-full items-center justify-between gap-4 px-5 py-4 text-left sm:px-6"
        aria-expanded={isOpen}
        aria-controls="package-presentation-checks-content"
        onClick={() => setIsOpen((open) => !open)}
      >
        <span className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-700">
            <Layers size={18} aria-hidden="true" />
          </span>
          <span>
            <span className="block text-sm font-extrabold uppercase tracking-wider text-slate-900">Package Presentation &amp; Readability Checks</span>
            <span className="mt-0.5 block text-xs font-medium text-slate-500">Rule 7, Rule 8 and Rule 9 verification details</span>
          </span>
        </span>
        <ChevronDown className={`package-presentation-chevron h-5 w-5 shrink-0 text-slate-500 ${isOpen ? 'is-open' : ''}`} aria-hidden="true" />
      </button>

      <div
        id="package-presentation-checks-content"
        className={`package-presentation-disclosure ${isOpen ? 'is-open' : ''}`}
        aria-hidden={!isOpen}
      >
        <div className="package-presentation-disclosure-inner">
          <div className="grid gap-3 border-t border-slate-200 p-5 sm:p-6 md:grid-cols-2 xl:grid-cols-3">
            {visualRuleEvaluations.map((visualRule, index) => {
              const status = getFriendlyVisualStatus(visualRule);
              const title = VISUAL_RULE_TITLES[visualRule.rule_id]
                || visualRule.title
                || visualRule.rule_id.replace(/_/g, ' ');
              return (
                <article key={`presentation-rule-${index}`} className="rounded-lg border border-slate-200 bg-slate-50/40 p-4 text-xs">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h3 className="font-bold leading-5 text-slate-800">{title}</h3>
                    <span className={`border px-2.5 py-1 text-[10px] font-bold uppercase ${getVisualStatusClass(status)}`}>{status}</span>
                  </div>
                  <p className="mt-3 leading-relaxed text-slate-600">{getVisualPresentationReason(visualRule.reason)}</p>
                  <p className="mt-3 border-t border-slate-200 pt-2 text-[11px] text-slate-500">{visualRule.legal_reference}</p>
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
};

export const EvidenceInspectorPanel = ({
  ruleEvaluations = [],
  aggregatedCandidates = [],
  captures = [],
  onSelectEvidence = null,
  regulatoryProductClass = 'UNKNOWN',
  foodLabelEvaluations = [],
  productOrigin = 'UNKNOWN',
  referenceDate = new Date().toISOString().slice(0, 10),
}) => {
  const [expandedReq, setExpandedReq] = useState(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState({});
  const [activeTab, setActiveTab] = useState('METROLOGY');
  const [ragQuery, setRagQuery] = useState('');
  const [ragLoading, setRagLoading] = useState(false);
  const [ragAnswer, setRagAnswer] = useState(null);
  const [ragError, setRagError] = useState('');

  const handleAskRag = async (queryText, domainText) => {
    setRagLoading(true);
    setRagError('');
    setRagAnswer(null);
    try {
      const data = await getGroundedExplanation(queryText, domainText, referenceDate);
      setRagAnswer(data);
    } catch {
      setRagError('Could not retrieve the legal explanation. Check the connection and try again.');
    } finally {
      setRagLoading(false);
    }
  };

  const toggleReq = (reqId) => {
    setExpandedReq(expandedReq === reqId ? null : reqId);
    setRagQuery('');
    setRagAnswer(null);
    setRagError('');
  };

  const toggleTechnical = (reqId, e) => {
    e.stopPropagation();
    setShowTechnicalDetails(prev => ({
      ...prev,
      [reqId]: !prev[reqId]
    }));
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'PASS':
      case 'OBSERVATION_CLEAR':
      case 'Complies':
      case '✓ Complies':
      case 'Compliant':
        return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-250';
      case 'FAIL':
      case 'Non-compliant':
      case 'Possible Violation':
      case '⚠ Possible Violation':
        return 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border-rose-250 font-bold';
      case 'REVIEW_REQUIRED':
      case 'Needs Officer Review':
      case 'NEEDS_RECAPTURE':
      case 'NOT_EVALUABLE':
      case 'Needs Review':
      case '⚠ Needs Review':
      case 'More Evidence Needed':
      case 'Take Another Photograph':
      case '📷 More Evidence Needed':
      case 'Not Evaluable From Image':
      case 'Physical Verification Required':
      case 'Inspector Verification Required':
      case 'Calibrated Measurement Required':
      case 'Controlled-Lighting Verification Required':
        return 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-250';
      case 'NOT_APPLICABLE':
      case 'Not Applicable':
      case '— Not Applicable':
      default:
        return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700';
    }
  };

  const getPresentationReason = (rule) => {
    if (!rule?.reason) return '';
    if (rule.rule_id === 'COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE') {
      return 'No explicit country-of-origin declaration was detected in the package evidence. The rule result uses the officer-provided product-origin classification shown separately below.';
    }
    if (rule.reason.includes("Supporting text 'None' was detected")) {
      return 'No reliable visual veg/non-veg symbol evidence was detected in the supplied photographs. Officer verification is required where applicable.';
    }
    return rule.reason.replace(
      'Corresponding FSSAI evaluation is not implemented yet.',
      'FSSAI business-name/address compliance requires officer review in the current inspection workflow.',
    );
  };

  const getFriendlyStatus = (status) => {
    switch (status) {
      case 'PASS':
      case 'OBSERVATION_CLEAR':
        return 'Compliant';
      case 'FAIL':
        return 'Non-compliant';
      case 'REVIEW_REQUIRED':
        return 'Needs Officer Review';
      case 'NEEDS_RECAPTURE':
      case 'NOT_EVALUABLE':
        return 'Take Another Photograph';
      case 'NOT_DETECTED':
        return 'Needs Officer Review';
      case 'DETECTED':
        return 'Package information detected';
      case 'NOT_APPLICABLE':
        return 'Not Applicable';
      default:
        return 'Needs Officer Review';
    }
  };

  // Helper to check whether usable visual geometry exists in captures for given evidence IDs
  const checkGeometryAvailability = (candOrEvidenceIds) => {
    const evIds = Array.isArray(candOrEvidenceIds)
      ? candOrEvidenceIds
      : candOrEvidenceIds?.evidence_ids || [];

    if (!evIds || evIds.length === 0) {
      return { hasGeometry: false, targetCaptureId: null, targetViewId: null };
    }

    for (const cap of captures) {
      const assessments = cap.visual_assessment?.assessments || [];
      for (const a of assessments) {
        if (a.evidence_ids?.some((id) => evIds.includes(id))) {
          const hasValidPolys = Array.isArray(a.polygons) && a.polygons.some(p => Array.isArray(p) && p.length >= 3);
          const hasValidBox = Boolean(a.geometry?.pixel_box && a.geometry.pixel_box.width_px > 0 && a.geometry.pixel_box.height_px > 0);
          if (hasValidPolys || hasValidBox) {
            return { hasGeometry: true, targetCaptureId: cap.capture_id, targetViewId: cap.view_id };
          }
        }
      }
    }

    return { hasGeometry: false, targetCaptureId: null, targetViewId: null };
  };

  // Resolve matching candidate and rule for a given requirement template
  const getRequirementMatch = (req, rulesList) => {
    // 1. Find matching candidates
    let matches = [];
    if (req.field === 'MANUFACTURER_PACKER_IMPORTER_DETAILS') {
      matches = aggregatedCandidates.filter(c => 
        c.field === 'MANUFACTURER_DETAILS' || 
        c.field === 'PACKER_DETAILS' || 
        c.field === 'IMPORTER_DETAILS' || 
        c.field === 'MANUFACTURER_PACKER_IMPORTER' ||
        c.field === 'MANUFACTURER_PACKER_IMPORTER_DETAILS'
      );
    } else if (req.field === 'MONTH_YEAR_MFG_PKD_IMPORT') {
      matches = aggregatedCandidates.filter(c => 
        c.field === 'MONTH_YEAR' || 
        c.field === 'MONTH_YEAR_MFG_PKD_IMPORT' ||
        c.field.startsWith('MONTH_YEAR')
      );
    } else if (req.field === 'CONSUMER_CARE_DETAILS') {
      matches = aggregatedCandidates.filter(c => 
        c.field === 'CONSUMER_CARE' ||
        c.field === 'CONSUMER_CARE_DETAILS' ||
        c.field.startsWith('CONSUMER_CARE')
      );
    } else {
      matches = aggregatedCandidates.filter(c => c.field === req.field);
    }

    // 2. Find matching presence rules
    let rules = [];
    if (req.ruleId === 'MANUFACTURER_PACKER_DECLARATION_PRESENCE' || req.ruleId === 'MANUFACTURER_PACKER_IMPORTER_DETAILS') {
      rules = rulesList.filter(r => 
        r.rule_id === 'MANUFACTURER_PACKER_DECLARATION_PRESENCE' ||
        r.rule_id === 'IMPORTER_DECLARATION_PRESENCE' ||
        r.rule_id === 'MANUFACTURER_DETAILS_ADDRESS_PRESENCE' || 
        r.rule_id === 'PACKER_DETAILS_ADDRESS_PRESENCE' || 
        r.rule_id === 'IMPORTER_DETAILS_ADDRESS_PRESENCE' || 
        r.rule_id === 'MANUFACTURER_PACKER_IMPORTER_DETAILS_PRESENCE' ||
        r.rule_id === 'MANUFACTURER_PACKER_IMPORTER_DETAILS'
      );
    } else if (req.ruleId === 'COMMON_GENERIC_NAME_DECLARATION_PRESENCE' || req.ruleId === 'COMMON_GENERIC_NAME_PRESENCE') {
      rules = rulesList.filter(r => 
        r.rule_id === 'COMMON_GENERIC_NAME_DECLARATION_PRESENCE' || 
        r.rule_id === 'COMMON_GENERIC_NAME_PRESENCE'
      );
    } else if (req.ruleId === 'COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE' || req.ruleId === 'COUNTRY_OF_ORIGIN_PRESENCE') {
      rules = rulesList.filter(r => 
        r.rule_id === 'COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE' || 
        r.rule_id === 'COUNTRY_OF_ORIGIN_PRESENCE'
      );
    } else if (req.ruleId === 'MONTH_YEAR_DECLARATION_PRESENCE') {
      rules = rulesList.filter(r => 
        r.rule_id === 'MONTH_YEAR_DECLARATION_PRESENCE' || 
        r.rule_id === 'MONTH_YEAR_PRESENCE'
      );
    } else if (req.ruleId === 'CONSUMER_CARE_DECLARATION_PRESENCE' || req.ruleId === 'CONSUMER_CARE_DETAILS_PRESENCE') {
      rules = rulesList.filter(r => 
        r.rule_id === 'CONSUMER_CARE_DECLARATION_PRESENCE' || 
        r.rule_id === 'CONSUMER_CARE_PHONE_PRESENCE' ||
        r.rule_id === 'CONSUMER_CARE_EMAIL_PRESENCE' ||
        r.rule_id === 'CONSUMER_CARE_DETAILS_PRESENCE' || 
        r.rule_id === 'CONSUMER_CARE_PRESENCE'
      );
    } else if (req.ruleId === 'UNIT_SALE_PRICE_DECLARATION_PRESENCE' || req.ruleId === 'UNIT_SALE_PRICE_PRESENCE') {
      rules = rulesList.filter(r => 
        r.rule_id === 'UNIT_SALE_PRICE_DECLARATION_PRESENCE' || 
        r.rule_id === 'UNIT_SALE_PRICE_PRESENCE'
      );
    } else {
      rules = rulesList.filter(r => r.rule_id === req.ruleId);
    }

    const primaryRule = rules[0] || null;
    const ruleStatus = primaryRule?.status || null;
    const candidateStatus = matches[0]?.status || null;
    
    // Resolve overall status
    let resolvedStatus = ruleStatus || candidateStatus || 'REVIEW_REQUIRED';
    if (rules.some(r => r.status === 'FAIL') || matches.some(m => m.status === 'FAIL')) {
      resolvedStatus = 'FAIL';
    } else if (rules.some(r => r.status === 'REVIEW_REQUIRED') || matches.some(m => m.status === 'REVIEW_REQUIRED')) {
      resolvedStatus = 'REVIEW_REQUIRED';
    } else if (rules.some(r => r.status === 'PASS') || matches.some(m => m.status === 'PASS')) {
      resolvedStatus = 'PASS';
    }

    // Combine values from detected candidates or primary rule evidence
    const detectedMatches = matches.filter(m => m.status !== 'NOT_DETECTED' && m.raw_value);
    let combinedValues = detectedMatches.length > 0
      ? detectedMatches.map(m => m.raw_value).join(' | ')
      : '';

    if (!combinedValues && primaryRule?.evidence_text) {
      combinedValues = primaryRule.evidence_text;
    }

    if (!combinedValues) {
      if (req.field === 'COUNTRY_OF_ORIGIN') {
        combinedValues = resolvedStatus === 'NOT_APPLICABLE'
          ? 'No explicit country-of-origin declaration detected in package evidence; requirement is not applicable for the confirmed context'
          : 'No explicit country-of-origin declaration detected in package evidence';
      } else if (resolvedStatus === 'NOT_APPLICABLE') {
        combinedValues = 'This requirement does not apply';
      } else if (resolvedStatus === 'FAIL') {
        combinedValues = 'Required declaration not found in the complete package evidence';
      } else {
        combinedValues = 'Could not read this declaration clearly from the available photographs';
      }
    }

    const evidenceIds = [
      ...new Set([
        ...(primaryRule?.evidence_ids || []),
        ...matches.flatMap(m => m.evidence_ids || [])
      ])
    ];

    return {
      rule: primaryRule,
      candidates: matches,
      value: combinedValues,
      status: resolvedStatus,
      evidenceIds: evidenceIds
    };
  };

  return (
    <div className="space-y-6">
      {/* Declaration Compliance Review Card */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-5 space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-700 pb-3">
          <FileText className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          <h3 className="text-sm font-extrabold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
            {activeTab === 'METROLOGY' ? 'Package declaration checks' : 'Food label checks'}
          </h3>
        </div>

        {regulatoryProductClass === 'FOOD' && (
          <div className="flex border-b border-slate-200 dark:border-slate-700 pb-1 gap-2">
            <button
              onClick={() => { setActiveTab('METROLOGY'); setExpandedReq(null); }}
              className={`flex-1 py-1.5 text-xs font-extrabold text-center rounded-lg transition-all ${
                activeTab === 'METROLOGY'
                  ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-200/50'
                  : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-900/40'
              }`}
            >
              Legal Metrology
            </button>
            <button
              onClick={() => { setActiveTab('FOOD'); setExpandedReq(null); }}
              className={`flex-1 py-1.5 text-xs font-extrabold text-center rounded-lg transition-all ${
                activeTab === 'FOOD'
                  ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-200/50'
                  : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-900/40'
              }`}
            >
              Food labelling (FSSAI)
            </button>
          </div>
        )}

        <div className="space-y-2">
          {(activeTab === 'METROLOGY' ? REQUIREMENTS : FOOD_REQUIREMENTS).map((req) => {
            const match = getRequirementMatch(req, activeTab === 'METROLOGY' ? ruleEvaluations : foodLabelEvaluations);
            const geomInfo = checkGeometryAvailability(match.evidenceIds);
            const isExpanded = expandedReq === req.id;
            const isTechnicalOpen = showTechnicalDetails[req.id];

            return (
              <div 
                key={req.id} 
                className={`border rounded-lg transition-all duration-200 ${
                  isExpanded 
                    ? 'border-indigo-400 dark:border-indigo-500 bg-indigo-50/10 dark:bg-indigo-950/10 shadow-sm' 
                    : 'border-slate-250 dark:border-slate-700 hover:bg-slate-50/30'
                }`}
              >
                {/* List Header */}
                <div 
                  onClick={() => toggleReq(req.id)}
                  className="flex items-center justify-between p-4 cursor-pointer select-none text-xs gap-3 flex-wrap"
                >
                  <div className="flex-1 min-w-0">
                    <span className="font-bold text-slate-800 dark:text-slate-200">
                      {req.name}
                    </span>
                    <span className="block text-[11px] text-slate-500 dark:text-slate-400 truncate mt-0.5">
                      {match.value}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                    <span className={`px-2.5 py-0.5 rounded font-bold uppercase text-[10px] border ${getStatusBadgeClass(getFriendlyStatus(match.status))}`}>
                      {getFriendlyStatus(match.status)}
                    </span>
                    <button 
                      onClick={() => toggleReq(req.id)}
                      className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-350"
                    >
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                  </div>
                </div>

                {/* Expanded Details Drawer */}
                {isExpanded && (
                  <div className="portal-result-reveal px-4 pb-4 border-t border-slate-100 dark:border-slate-700 pt-3.5 space-y-4 text-xs">
                    <div>
                      <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Regulatory provision</h4>
                      <p className="text-slate-750 dark:text-slate-300 leading-relaxed">{req.desc}</p>
                    </div>

                    <div>
                      <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Detected package evidence</h4>
                      <div className="text-slate-800 dark:text-slate-200 bg-slate-50 dark:bg-slate-900/60 p-2.5 rounded border border-slate-200/50 dark:border-slate-800/60 leading-relaxed break-words whitespace-pre-wrap">
                        {match.value}
                      </div>
                    </div>

                    {match.rule?.reason && (
                      <div>
                        <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Reason for finding</h4>
                        <p className="text-slate-755 dark:text-slate-300 leading-relaxed bg-slate-50/50 dark:bg-slate-900/20 p-2 rounded">
                          {getPresentationReason(match.rule)}
                        </p>
                      </div>
                    )}

                    <div>
                      <h4 className="mb-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">Officer action</h4>
                      <p className="leading-relaxed text-slate-700 dark:text-slate-300">
                        {match.status === 'FAIL'
                          ? 'Review the detected evidence and record the appropriate enforcement action.'
                          : match.status === 'REVIEW_REQUIRED'
                            ? 'Confirm the declaration against the package photograph before finalization.'
                            : match.status === 'PASS'
                              ? 'No further action is required unless the officer observes contradictory package evidence.'
                              : 'Record the applicability decision in the inspection record.'}
                      </p>
                    </div>

                    {req.field === 'COUNTRY_OF_ORIGIN' && (
                      <div>
                        <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Officer-provided context</h4>
                        <p className="text-slate-700 dark:text-slate-300">
                          Product Origin Classification: {productOrigin === 'UNKNOWN' ? 'Unknown / not established' : productOrigin.replace(/_/g, ' ').toLowerCase()}
                        </p>
                      </div>
                    )}

                    <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 dark:border-slate-700/60">
                      <div>
                        {match.rule?.legal_reference && (
                          <span className="text-[10px] text-slate-500 font-medium bg-slate-100 dark:bg-slate-750 px-2 py-0.5 rounded" title={match.rule.legal_reference}>
                            {match.rule.legal_reference}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3">
                        {geomInfo.hasGeometry && onSelectEvidence ? (
                          <button
                            onClick={() => {
                              onSelectEvidence(match.evidenceIds, geomInfo.targetCaptureId, geomInfo.targetViewId, null, req.field);
                            }}
                            className="inline-flex items-center gap-1 font-bold text-indigo-600 dark:text-indigo-400 hover:underline"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>View supporting photograph</span>
                          </button>
                        ) : match.evidenceIds?.length > 0 ? (
                          <span className="text-[10px] text-slate-400 dark:text-slate-500 italic">
                            Supporting location could not be shown
                          </span>
                        ) : null}

                        <button
                          onClick={(e) => toggleTechnical(req.id, e)}
                          className="inline-flex items-center gap-1 font-semibold text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                        >
                          <Info className="w-3.5 h-3.5" />
                          <span>{isTechnicalOpen ? 'Hide details' : 'View details'}</span>
                        </button>
                      </div>
                    </div>

                    {/* Collapsible Technical Details (Internal metadata) */}
                    {isTechnicalOpen && (
                      <div className="portal-result-reveal bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-lg p-3 space-y-2.5 font-mono text-[10px] text-slate-600 dark:text-slate-400">
                        <div className="flex justify-between border-b border-slate-200/40 pb-1">
                          <span>Rule Code:</span>
                          <span className="font-bold text-slate-800 dark:text-slate-200">{match.rule?.rule_id || req.ruleId}</span>
                        </div>
                        {match.candidates?.map((cand, cIdx) => (
                          <div key={cIdx} className="space-y-1 bg-white dark:bg-slate-800/40 p-2 rounded border border-slate-200/20">
                            <div className="font-bold text-slate-700 dark:text-slate-300">Recorded item #{cIdx + 1}: {cand.field}</div>
                            <div>Recorded package text: {cand.raw_value || '—'}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* RAG Regulatory assistant action */}
                    <div className="border-t border-slate-100 dark:border-slate-700/60 pt-3.5 mt-3 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Legal provision help</h4>
                        <button
                          onClick={() => {
                            const query = `What does ${req.name} (Rule: ${req.ruleId}) require?`;
                            setRagQuery(query);
                            handleAskRag(query, activeTab === 'METROLOGY' ? 'LEGAL_METROLOGY' : 'FOOD_LABEL_FSSAI');
                          }}
                          className="legal-help-button px-3 py-1.5 text-[10px]"
                        >
                          Explain this requirement
                        </button>
                      </div>

                      {/* Assistant query input */}
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="Ask about this legal requirement..."
                          value={ragQuery}
                          onChange={(e) => setRagQuery(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && e.target.value.trim()) {
                              handleAskRag(e.target.value, activeTab === 'METROLOGY' ? 'LEGAL_METROLOGY' : 'FOOD_LABEL_FSSAI');
                            }
                          }}
                          className="flex-1 px-3 py-1.5 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                        />
                        <button
                          onClick={() => {
                            if (ragQuery.trim()) {
                              handleAskRag(ragQuery, activeTab === 'METROLOGY' ? 'LEGAL_METROLOGY' : 'FOOD_LABEL_FSSAI');
                            }
                          }}
                          className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-bold cursor-pointer transition-colors"
                        >
                          Ask
                        </button>
                      </div>

                      {/* Display response */}
                      {ragLoading && (
                        <div className="text-slate-500 text-[10px] animate-pulse">Retrieving legal guidance...</div>
                      )}
                      {ragError && (
                        <div className="text-rose-500 text-[10px]">{ragError}</div>
                      )}
                      {ragAnswer && (
                        <div className="portal-result-reveal bg-indigo-50/40 dark:bg-slate-900/40 border border-indigo-100/30 dark:border-slate-800 rounded p-3 space-y-2">
                          <p className="text-slate-800 dark:text-slate-200 leading-relaxed font-sans text-xs italic">
                            {ragAnswer.answer}
                          </p>
                          {ragAnswer.sources?.length > 0 && (
                            <div className="text-[10px] text-slate-500 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/80 pt-2 flex flex-wrap gap-3">
                              {ragAnswer.sources.map((s, sIdx) => (
                                <div key={sIdx}>
                                  <span className="font-semibold text-slate-700 dark:text-slate-350">Official Source: </span>
                                  {s.title} ({s.provision_number})
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
};

export default EvidenceInspectorPanel;
