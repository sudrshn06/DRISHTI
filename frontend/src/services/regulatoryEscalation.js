const FINDING_GROUPS = [
  ['LEGAL_METROLOGY', 'rule_evaluations'],
  ['FOOD_LABEL_FSSAI', 'food_label_evaluations'],
  ['VISUAL_PRESENTATION', 'visual_rule_evaluations'],
];

const FINALIZED_FINDING_GROUPS = [
  ['LEGAL_METROLOGY', 'declaration_findings'],
  ['FOOD_LABEL_FSSAI', 'food_label_findings'],
  ['VISUAL_PRESENTATION', 'visual_compliance_findings'],
];

const unique = (values) => [...new Set(values.filter(Boolean))];

const humanize = (value) => String(value || '')
  .replace(/_/g, ' ')
  .replace(/\b\w/g, (character) => character.toUpperCase());

const candidateValue = (candidate) => {
  if (candidate?.raw_value) return candidate.raw_value;
  const normalized = candidate?.normalized_value;
  if (!normalized) return '';
  if (typeof normalized === 'string') return normalized;
  return Object.values(normalized).filter((value) => value != null && value !== '').join(' · ');
};

const evaluatedValueText = (value) => {
  if (value == null || value === '') return '';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (Array.isArray(value)) return unique(value.map(evaluatedValueText)).join(' · ');
  if (typeof value === 'object') {
    if (value.raw_value) return evaluatedValueText(value.raw_value);
    if (value.observed_values) return evaluatedValueText(value.observed_values);
    return unique(Object.values(value).map(evaluatedValueText)).join(' · ');
  }
  return '';
};

export const getConfirmedFailFindings = (session) => {
  const source = session?.report_snapshot || session;
  const groups = session?.report_snapshot ? FINALIZED_FINDING_GROUPS : FINDING_GROUPS;
  return groups.flatMap(([domain, key]) => (
    (source?.[key] || [])
    .filter((finding) => finding.status === 'FAIL')
    .map((finding) => ({ ...finding, domain }))
  ));
};

export const isRegulatoryEscalationAvailable = (session) => (
  session?.lifecycle_status === 'FINALIZED' && getConfirmedFailFindings(session).length > 0
);

export const getCandidate = (session, field) => {
  const matches = (candidates) => (candidates || []).find((candidate) => (
    candidate.field === field && candidate.status === 'DETECTED'
  ));
  return matches(session?.report_snapshot?.extracted_evidence)
    || matches(session?.aggregated_candidates);
};

export const getProductIdentity = (session) => ({
  product: candidateValue(
    getCandidate(session, 'COMMON_GENERIC_NAME')
      || getCandidate(session, 'PRODUCT_NAME'),
  ) || 'Not recorded',
  brand: candidateValue(
    getCandidate(session, 'BRAND_NAME')
      || getCandidate(session, 'BRAND'),
  ) || '',
});

export const getFindingPresentation = (session, finding) => {
  const evidenceIds = unique(finding.evidence_ids || []);
  const directCaptureIds = finding.capture_ids || [];
  const candidates = session?.aggregated_candidates || [];
  const evidenceCandidates = candidates.filter((candidate) => (
    (candidate.evidence_ids || []).some((id) => evidenceIds.includes(id))
  ));
  const relatedCandidates = evidenceCandidates.length
    ? evidenceCandidates
    : candidates.filter((candidate) => candidate.field === finding.field);
  const candidateCaptureIds = relatedCandidates.flatMap((candidate) => candidate.capture_ids || []);
  const evidenceCaptures = (session?.captures || []).filter((capture) => (
    evidenceIds.includes(capture.evidence_id)
    || (capture.field_candidates || []).some((candidate) => (
      (candidate.evidence_ids || []).some((id) => evidenceIds.includes(id))
    ))
  ));
  const captureIds = evidenceCaptures.length
    ? evidenceCaptures.map((capture) => capture.capture_id)
    : unique([...directCaptureIds, ...candidateCaptureIds]);
  const sourceViews = unique((session?.captures || [])
    .filter((capture) => captureIds.includes(capture.capture_id))
    .map((capture) => capture.view_id));
  const observedCandidate = relatedCandidates.find((candidate) => candidate.raw_value)
    || relatedCandidates[0];
  const evaluatedValue = finding.evaluated_value;
  const observedValue = candidateValue(observedCandidate)
    || evaluatedValueText(evaluatedValue)
    || 'No observed value recorded';

  return {
    title: humanize(finding.title || finding.field || finding.rule_id || 'Confirmed requirement failure'),
    legalReference: finding.source_reference || finding.legal_reference || '',
    reason: finding.reason || 'No deterministic explanation was recorded.',
    observedValue,
    evidenceIds,
    sourceViews,
  };
};

export const buildRegulatoryEscalationSummary = (session) => {
  const findings = getConfirmedFailFindings(session);
  const { product, brand } = getProductIdentity(session);
  const lines = [
    'DRISHTI REGULATORY ESCALATION SUMMARY',
    `Product: ${product}`,
    ...(brand ? [`Brand: ${brand}`] : []),
    `Inspection reference: ${session?.inspection_id || 'Not recorded'}`,
    '',
    'Confirmed failed requirements:',
  ];

  findings.forEach((finding, index) => {
    const item = getFindingPresentation(session, finding);
    lines.push(`${index + 1}. ${item.title}`);
    lines.push(`   Legal reference: ${item.legalReference || 'Not recorded in the finalized finding'}`);
    lines.push(`   Deterministic explanation: ${item.reason}`);
    lines.push(`   Observed evidence: ${item.observedValue}`);
    if (item.sourceViews.length) lines.push(`   Source view: ${item.sourceViews.map(humanize).join(', ')}`);
    if (item.evidenceIds.length) lines.push(`   Evidence references: ${item.evidenceIds.join(', ')}`);
  });

  lines.push('', 'Officer-controlled handoff only. DRISHTI has not submitted a complaint.');
  return lines.join('\n');
};

export const formatEscalationDate = (session) => {
  const value = session?.report_snapshot?.metadata?.generated_at;
  if (!value) return 'Not recorded';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
};

export const formatFindingLabel = humanize;
