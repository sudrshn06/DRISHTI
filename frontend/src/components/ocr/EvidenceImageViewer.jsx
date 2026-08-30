import React from 'react';
import { Camera, AlertCircle, CheckCircle2, EyeOff } from 'lucide-react';
import EvidenceOverlay from './EvidenceOverlay';

/**
 * EvidenceImageViewer handles multi-view image rendering, overlay alignment,
 * and view-switching synchronization for inspector evidence examination.
 */
export const EvidenceImageViewer = ({
  views = [],
  captures = [],
  activeViewId = 'FRONT',
  onSelectView = null,
  selectedEvidenceIds = [],
  selectedFinding = null,
  selectedFieldName = null,
  imageUrls = {}, // map of capture_id or view_id -> string object URL
  imageLoadStates = {},
  onRetryImage = null,
  onUploadCapture = null,
  isUploading = false,
  onSelectEvidence = null
}) => {
  const handleFileSelection = (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) onUploadCapture(activeViewId, file);
  };

  // Find current active capture
  const capturesForActiveView = captures.filter((c) => c.view_id === activeViewId);
  const activeCapture = capturesForActiveView[capturesForActiveView.length - 1];

  const activeViewConfig = views.find((v) => v.view_id === activeViewId);
  const imageUrl = activeCapture
    ? (imageUrls[activeCapture.capture_id] || imageUrls[activeViewId])
    : imageUrls[activeViewId] || null;
  const imageLoadState = activeCapture ? imageLoadStates[activeCapture.capture_id] : null;

  const visualSummary = activeCapture?.visual_assessment;
  const imageWidth = visualSummary?.image_width || 1000;
  const imageHeight = visualSummary?.image_height || 1000;

  // Check if selected evidence has geometry in active capture
  const selectedEvidenceSet = new Set(selectedEvidenceIds || []);
  const matchingAssessment = visualSummary?.assessments?.find((a) =>
    a.evidence_ids?.some((id) => selectedEvidenceSet.has(id))
  );
  const hasGeometry = matchingAssessment && matchingAssessment.polygons && matchingAssessment.polygons.length > 0;
  const isEvidenceSelected = selectedEvidenceIds && selectedEvidenceIds.length > 0;

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
      {/* View Tabs */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-700 px-4 py-2.5 bg-slate-50 dark:bg-slate-900/50">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {views.map((v) => {
            const hasCapture = captures.some((c) => c.view_id === v.view_id);
            const isActive = v.view_id === activeViewId;

            return (
              <button
                key={v.view_id}
                onClick={() => onSelectView && onSelectView(v.view_id)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : hasCapture
                    ? 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-100'
                    : 'text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                }`}
              >
                {hasCapture && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                <span>{v.display_name}</span>
                {!v.required && <span className="text-[10px] opacity-70">(optional)</span>}
              </button>
            );
          })}
        </div>

      </div>

      {/* Main Image & Overlay Canvas Container */}
      <div className="relative min-h-[280px] max-h-[550px] bg-slate-950 flex items-center justify-center p-2 sm:min-h-[380px]">
        {imageUrl ? (
          <div className="relative inline-block max-w-full max-h-[530px] rounded overflow-hidden shadow-inner">
            <img
              src={imageUrl}
              alt={`${activeViewConfig?.display_name || activeViewId} Package View`}
              className="max-h-[530px] w-auto object-contain block select-none"
            />
            {/* SVG Evidence Overlay */}
            <EvidenceOverlay
              width={imageWidth}
              height={imageHeight}
              assessments={visualSummary?.assessments || []}
              findings={visualSummary?.findings || []}
              selectedEvidenceIds={selectedEvidenceIds}
              selectedFinding={selectedFinding}
              onSelectEvidence={onSelectEvidence}
            />
          </div>
        ) : activeCapture ? (
          <div className="space-y-4 p-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-slate-400">
              {imageLoadState === 'unavailable'
                ? <AlertCircle className="h-6 w-6" />
                : <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-500 border-t-white" />}
            </div>
            <div>
              <p className="text-sm font-medium text-slate-200">
                {imageLoadState === 'unavailable' ? 'Could not load the saved photograph' : 'Loading saved photograph…'}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                {imageLoadState === 'unavailable' ? 'Check the connection and try again.' : 'The inspection record is available while the photograph is retrieved.'}
              </p>
            </div>
            {imageLoadState === 'unavailable' && onRetryImage && (
              <button type="button" onClick={() => onRetryImage(activeCapture)} className="min-h-12 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white hover:bg-indigo-700">
                Retry photograph
              </button>
            )}
          </div>
        ) : (
          <div className="text-center p-8 space-y-4">
            <div className="w-12 h-12 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center mx-auto">
              <Camera className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-300">Photograph the {activeViewConfig?.display_name || activeViewId} side</p>
              <p className="text-xs text-slate-500 mt-1">Keep the label flat, well lit, and fully inside the frame.</p>
            </div>
            {onUploadCapture && (
              <label className="inline-flex min-h-12 cursor-pointer items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white shadow transition-colors hover:bg-indigo-700">
                <Camera className="w-4 h-4" />
                <span>Take {activeViewConfig?.display_name} photograph</span>
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={handleFileSelection}
                  disabled={isUploading}
                />
              </label>
            )}
          </div>
        )}
      </div>

      {/* Bottom Status / Selection Bar */}
      <div className="p-3 bg-white dark:bg-slate-800 border-t border-slate-100 dark:border-slate-700 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          {activeCapture ? (() => {
            const isAcceptable = activeCapture.status === 'ACCEPTABLE' || activeCapture.status === 'ACCEPTED';
            const isReview = activeCapture.status === 'NEEDS_REVIEW'
              || activeCapture.status === 'RECAPTURE_RECOMMENDED'
              || activeCapture.status === 'RETAKE_RECOMMENDED';
            const badgeClass = isAcceptable
              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
              : isReview
              ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
              : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';

            return (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-medium ${badgeClass}`}>
                {isAcceptable ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                {isAcceptable ? 'Photograph saved' : isReview ? 'Take another photograph' : 'Photograph needs attention'}
              </span>
            );
          })() : imageUrl ? (
            <span className="rounded bg-amber-50 px-2 py-1 font-semibold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">Waiting to upload — not yet saved</span>
          ) : (
            <span className="text-slate-400">Photograph not yet taken</span>
          )}

          {isEvidenceSelected && (
            <span className="text-slate-600 dark:text-slate-300 font-medium">
              Target: <span className="font-semibold text-indigo-600 dark:text-indigo-400">{selectedFieldName ? selectedFieldName.replace(/_/g, ' ') : 'Declaration'}</span>
            </span>
          )}
        </div>

        {/* Missing Geometry Safe Fallback Indicator */}
        {isEvidenceSelected && !hasGeometry && (
          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 font-medium text-[11px]">
            <EyeOff className="w-3 h-3" />
            <span>Supporting location could not be shown</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default EvidenceImageViewer;
