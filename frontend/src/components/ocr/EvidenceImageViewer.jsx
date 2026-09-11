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
  imageUrls = {},
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

  const selectedEvidenceSet = new Set(selectedEvidenceIds || []);
  const matchingAssessment = visualSummary?.assessments?.find((a) =>
    a.evidence_ids?.some((id) => selectedEvidenceSet.has(id))
  );
  const hasGeometry = matchingAssessment && matchingAssessment.polygons && matchingAssessment.polygons.length > 0;
  const isEvidenceSelected = selectedEvidenceIds && selectedEvidenceIds.length > 0;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_12px_30px_rgba(16,42,67,0.07)] dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/90 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/50">
        <div className="flex min-w-0 items-center gap-1.5 overflow-x-auto pr-2">
          {views.map((v) => {
            const hasCapture = captures.some((c) => c.view_id === v.view_id);
            const isActive = v.view_id === activeViewId;

            return (
              <button
                key={v.view_id}
                onClick={() => onSelectView && onSelectView(v.view_id)}
                className={`flex min-h-10 items-center gap-1.5 whitespace-nowrap rounded-xl px-3 py-2 text-xs font-bold transition-all ${
                  isActive
                    ? 'bg-[#102a43] text-white shadow-sm'
                    : hasCapture
                      ? 'border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
                      : 'text-slate-400 hover:bg-white hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300'
                }`}
              >
                {hasCapture && <CheckCircle2 className={`h-3.5 w-3.5 ${isActive ? 'text-emerald-300' : 'text-emerald-500'}`} />}
                <span>{v.display_name}</span>
                {!v.required && <span className="text-[10px] opacity-70">optional</span>}
              </button>
            );
          })}
        </div>
      </div>

      <div className="relative flex min-h-[280px] max-h-[550px] items-center justify-center bg-[#0b1724] p-3 sm:min-h-[400px]">
        {imageUrl ? (
          <div className="relative inline-block max-h-[525px] max-w-full overflow-hidden rounded-xl border border-white/10 bg-black shadow-[0_16px_36px_rgba(0,0,0,0.25)]">
            <img
              src={imageUrl}
              alt={`${activeViewConfig?.display_name || activeViewId} Package View`}
              className="block max-h-[525px] w-auto select-none object-contain"
            />
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
          <div className="max-w-md space-y-4 p-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 text-slate-300 ring-1 ring-white/10">
              {imageLoadState === 'unavailable'
                ? <AlertCircle className="h-6 w-6" />
                : <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-500 border-t-white" />}
            </div>
            <div>
              <p className="text-sm font-bold text-slate-100">{imageLoadState === 'unavailable' ? 'Could not load the saved photograph' : 'Loading saved photograph…'}</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">{imageLoadState === 'unavailable' ? 'Check the connection and try again.' : 'The inspection record remains available while the photograph is retrieved.'}</p>
            </div>
            {imageLoadState === 'unavailable' && onRetryImage && (
              <button type="button" onClick={() => onRetryImage(activeCapture)} className="min-h-12 rounded-xl bg-[#087f83] px-5 py-3 text-sm font-extrabold text-white hover:bg-[#066f73]">Retry photograph</button>
            )}
          </div>
        ) : (
          <div className="max-w-md space-y-4 p-8 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 text-slate-300 ring-1 ring-white/10">
              <Camera className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-200">Photograph the {activeViewConfig?.display_name || activeViewId} side</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">Keep the label flat, well lit, sharp, and fully inside the frame.</p>
            </div>
            {onUploadCapture && (
              <label className="inline-flex min-h-12 cursor-pointer items-center gap-2 rounded-xl bg-[#087f83] px-5 py-3 text-sm font-extrabold text-white shadow transition-colors hover:bg-[#066f73]">
                <Camera className="h-4 w-4" />
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

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 bg-white px-4 py-3 text-xs dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-wrap items-center gap-2">
          {activeCapture ? (() => {
            const isAcceptable = activeCapture.status === 'ACCEPTABLE' || activeCapture.status === 'ACCEPTED';
            const isReview = activeCapture.status === 'NEEDS_REVIEW'
              || activeCapture.status === 'RECAPTURE_RECOMMENDED'
              || activeCapture.status === 'RETAKE_RECOMMENDED';
            const badgeClass = isAcceptable
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
              : isReview
                ? 'border-amber-200 bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
                : 'border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';

            return (
              <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 font-bold ${badgeClass}`}>
                {isAcceptable ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
                {isAcceptable ? 'Photograph saved' : isReview ? 'Another photograph recommended' : 'Photograph needs attention'}
              </span>
            );
          })() : imageUrl ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 font-bold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">Waiting to upload — not yet saved</span>
          ) : (
            <span className="font-medium text-slate-400">Photograph not yet taken</span>
          )}

          {isEvidenceSelected && (
            <span className="font-medium text-slate-600 dark:text-slate-300">Target: <span className="font-bold text-[#087f83]">{selectedFieldName ? selectedFieldName.replace(/_/g, ' ') : 'Declaration'}</span></span>
          )}
        </div>

        {isEvidenceSelected && !hasGeometry && (
          <div className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
            <EyeOff className="h-3 w-3" />
            <span>Supporting location could not be shown</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default EvidenceImageViewer;
