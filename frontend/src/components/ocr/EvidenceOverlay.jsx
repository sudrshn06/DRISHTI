import React from 'react';

/**
 * EvidenceOverlay renders scalable vector annotations directly over the package image.
 * Uses image natural coordinate space via SVG viewBox for perfect responsive alignment.
 */
export const EvidenceOverlay = ({
  width = 1000,
  height = 1000,
  assessments = [],
  findings = [],
  selectedEvidenceIds = [],
  selectedFinding = null,
  onSelectEvidence = null
}) => {
  if (!width || !height || width <= 0 || height <= 0) {
    return null;
  }

  const selectedEvidenceSet = new Set(selectedEvidenceIds || []);

  // Format polygon points array [[x1, y1], [x2, y2], ...] into SVG points string "x1,y1 x2,y2 ..."
  const formatPolygonPoints = (poly) => {
    if (!Array.isArray(poly) || poly.length < 3) return null;
    const validPoints = poly
      .filter((pt) => Array.isArray(pt) && pt.length >= 2 && !isNaN(pt[0]) && !isNaN(pt[1]))
      .map((pt) => `${pt[0]},${pt[1]}`);
    return validPoints.length >= 3 ? validPoints.join(' ') : null;
  };

  // Find Net Quantity Clearance finding if selected or present
  const clearanceFinding = selectedFinding?.check_type === 'NET_QUANTITY_CLEARANCE'
    ? selectedFinding
    : findings?.find((f) => f.check_type === 'NET_QUANTITY_CLEARANCE' && selectedEvidenceSet.size > 0 && f.evidence_ids?.some(id => selectedEvidenceSet.has(id)));

  const clearanceBox = clearanceFinding?.metrics?.clearance_box_px;
  const interferingList = clearanceFinding?.interfering_evidence || [];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="absolute inset-0 w-full h-full pointer-events-none select-none"
      preserveAspectRatio="none"
    >
      <defs>
        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {/* 1. Base Declaration Polygons */}
      {assessments?.map((assessment, aIdx) => {
        const isSelected = assessment.evidence_ids?.some((id) => selectedEvidenceSet.has(id));
        const isClipped = assessment.geometry?.touches_edge;

        return (
          <g key={`assessment-${aIdx}`} className="transition-all duration-200">
            {assessment.polygons?.map((poly, pIdx) => {
              const pointsStr = formatPolygonPoints(poly);
              if (!pointsStr) return null;

              if (isSelected) {
                return (
                  <polygon
                    key={`poly-${aIdx}-${pIdx}`}
                    points={pointsStr}
                    fill="rgba(79, 70, 229, 0.25)"
                    stroke="#4F46E5"
                    strokeWidth="3"
                    strokeLinejoin="round"
                    filter="url(#glow)"
                    className="pointer-events-auto cursor-pointer"
                    onClick={() => onSelectEvidence && onSelectEvidence(assessment.evidence_ids, assessment.capture_id, assessment.view_id, null, assessment.field)}
                  />
                );
              }

              const hasActiveSelection = selectedEvidenceSet.size > 0;

              return (
                <polygon
                  key={`poly-${aIdx}-${pIdx}`}
                  points={pointsStr}
                  fill={isClipped ? 'rgba(239, 68, 68, 0.08)' : hasActiveSelection ? 'none' : 'rgba(59, 130, 246, 0.05)'}
                  stroke={isClipped ? '#EF4444' : '#3B82F6'}
                  strokeWidth={hasActiveSelection ? '1' : '1.5'}
                  strokeDasharray={isClipped ? '4 2' : hasActiveSelection ? '2 2' : undefined}
                  strokeOpacity={hasActiveSelection ? '0.3' : '0.65'}
                  className="pointer-events-auto cursor-pointer hover:stroke-indigo-500 hover:stroke-opacity-100 hover:fill-indigo-500/10"
                  onClick={() => onSelectEvidence && onSelectEvidence(assessment.evidence_ids, assessment.capture_id, assessment.view_id, null, assessment.field)}
                />
              );
            })}

            {/* Selected Label Badge */}
            {isSelected && assessment.geometry?.pixel_box && (
              <g transform={`translate(${assessment.geometry.pixel_box.x_min}, ${Math.max(16, assessment.geometry.pixel_box.y_min - 6)})`}>
                <rect
                  x="0"
                  y="-16"
                  width={Math.max(60, (assessment.field?.length || 8) * 8 + 12)}
                  height="18"
                  rx="4"
                  fill="#4F46E5"
                />
                <text
                  x="6"
                  y="-4"
                  fill="#FFFFFF"
                  fontSize="11"
                  fontWeight="bold"
                  fontFamily="sans-serif"
                >
                  {assessment.field?.replace(/_/g, ' ')}
                </text>
              </g>
            )}
          </g>
        );
      })}

      {/* 2. Rule 8 Clearance Zone Box Overlay */}
      {clearanceBox && (
        <g className="transition-all duration-300">
          <rect
            x={clearanceBox.x_min}
            y={clearanceBox.y_min}
            width={Math.max(0, clearanceBox.x_max - clearanceBox.x_min)}
            height={Math.max(0, clearanceBox.y_max - clearanceBox.y_min)}
            fill="rgba(245, 158, 11, 0.12)"
            stroke="#F59E0B"
            strokeWidth="2"
            strokeDasharray="6 3"
            rx="4"
          />
          <text
            x={clearanceBox.x_min + 4}
            y={Math.max(14, clearanceBox.y_min - 4)}
            fill="#D97706"
            fontSize="10"
            fontWeight="bold"
            fontFamily="sans-serif"
          >
            Rule 8 Clearance Zone (1x vertical, 2x horizontal)
          </text>
        </g>
      )}

      {/* 3. Interfering OCR Polygons in Clearance Zone */}
      {interferingList?.map((inter, iIdx) => {
        const pointsStr = formatPolygonPoints(inter.polygon);
        if (!pointsStr) return null;

        return (
          <g key={`interfering-${iIdx}`}>
            <polygon
              points={pointsStr}
              fill="rgba(239, 68, 68, 0.3)"
              stroke="#EF4444"
              strokeWidth="2.5"
              strokeLinejoin="round"
            />
          </g>
        );
      })}
    </svg>
  );
};

export default EvidenceOverlay;
