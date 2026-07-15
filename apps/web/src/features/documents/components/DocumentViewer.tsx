"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import { Document, Page, pdfjs } from "react-pdf";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import { ZoomIn, ZoomOut, Maximize } from "lucide-react";
import { ExtractedDocument, Bbox } from "@/types";
import { Button } from "@/components/ui/button";
import { resolveDocumentEvidence } from "../documents.api";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Set worker path for react-pdf
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface DocumentViewerProps {
  document: ExtractedDocument;
  focusedBbox?: Bbox;
}

export function DocumentViewer({ document, focusedBbox }: DocumentViewerProps) {
  const [numPages, setNumPages] = useState<number>();
  const [pageNumber, setPageNumber] = useState(1);
  const [evidenceUrl, setEvidenceUrl] = useState(document.fileUrl);
  // Default natural width for scaling overlays
  const [renderedWidth, setRenderedWidth] = useState<number>(600);

  useEffect(() => {
    let active = true;
    resolveDocumentEvidence(document.fileUrl)
      .then(url => { if (active) setEvidenceUrl(url); })
      .catch(() => { if (active) setEvidenceUrl(""); });
    return () => { active = false; };
  }, [document.fileUrl]);

  useEffect(() => {
    if (focusedBbox?.page && focusedBbox.page > 0) setPageNumber(focusedBbox.page);
  }, [focusedBbox?.page]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }): void {
    setNumPages(numPages);
  }

  // To map the BBOX (which we assume is relative 0-1 or absolute based on some standard width)
  // For MVP, assuming bbox x,y,w,h are in absolute pixels relative to a standard 600px width.
  const scale = renderedWidth / 600; 

  const renderBboxOverlay = () => {
    if (!focusedBbox) return null;
    return (
      <div
        className="absolute border-2 border-[var(--royal)] bg-[var(--royal)]/10 z-10 transition-all duration-300 ease-in-out pointer-events-none rounded-sm"
        style={{
          left: `${focusedBbox.x * scale}px`,
          top: `${focusedBbox.y * scale}px`,
          width: `${focusedBbox.w * scale}px`,
          height: `${focusedBbox.h * scale}px`,
        }}
      />
    );
  };

  return (
    <div className="flex flex-col h-full bg-[var(--canvas)] overflow-hidden relative">
      {/* Viewer Toolbar */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 bg-[var(--panel)] border border-[var(--hairline)] text-[var(--text)] px-4 py-2 rounded-full shadow-lg">
        {/* We will rely on TransformWrapper for zoom controls */}
        <span className="text-xs font-medium px-2">
          {document.fileType.toUpperCase()}
        </span>
        {document.fileType === "pdf" && numPages && (
          <span className="text-xs border-l border-[var(--hairline)] pl-4 pr-2">
            Page {pageNumber} of {numPages}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-hidden relative">
        <TransformWrapper
          initialScale={1}
          minScale={0.5}
          maxScale={4}
          centerOnInit={true}
        >
          {({ zoomIn, zoomOut, resetTransform }) => (
            <>
              {/* Zoom Controls */}
              <div className="absolute top-4 right-4 z-20 flex flex-col gap-2">
                <Button aria-label="Zoom in" variant="secondary" size="icon" className="h-11 w-11 rounded-full shadow" onClick={() => zoomIn()}>
                  <ZoomIn className="h-4 w-4" />
                </Button>
                <Button aria-label="Zoom out" variant="secondary" size="icon" className="h-11 w-11 rounded-full shadow" onClick={() => zoomOut()}>
                  <ZoomOut className="h-4 w-4" />
                </Button>
                <Button aria-label="Reset zoom" variant="secondary" size="icon" className="h-11 w-11 rounded-full shadow" onClick={() => resetTransform()}>
                  <Maximize className="h-4 w-4" />
                </Button>
              </div>

              <TransformComponent wrapperClass="!w-full !h-full" contentClass="!w-full !h-full flex items-center justify-center p-8">
                <div 
                  className="relative shadow-xl bg-white transition-transform origin-top-left"
                  ref={(el) => {
                    if (el) setRenderedWidth(el.clientWidth);
                  }}
                >
                  {!evidenceUrl ? (
                    <div className="w-[600px] h-[800px] flex items-center justify-center text-sm text-[var(--muted)] font-medium bg-white">
                      Preview unavailable
                    </div>
                  ) : document.fileType === "pdf" ? (
                    <Document
                      file={evidenceUrl}
                      onLoadSuccess={onDocumentLoadSuccess}
                      className="max-w-full"
                      loading={
                        <div className="w-[600px] h-[800px] flex items-center justify-center text-sm text-[var(--muted)]">
                          Loading PDF...
                        </div>
                      }
                      error={
                        <div className="flex h-[800px] w-[600px] items-center justify-center text-sm text-[var(--muted)]">
                          Preview unavailable
                        </div>
                      }
                    >
                      <Page
                        pageNumber={pageNumber}
                        width={600}
                        renderTextLayer={false}
                        renderAnnotationLayer={false}
                      />
                    </Document>
                  ) : document.fileType === "image" ? (
                    <Image
                      src={evidenceUrl} 
                      alt="Document Preview" 
                      width={600}
                      height={800}
                      unoptimized
                      className="w-[600px] object-contain bg-white"
                      onError={() => setEvidenceUrl("")}
                    />
                  ) : (
                    <div className="flex h-[480px] w-[600px] flex-col items-center justify-center gap-2 bg-white p-8 text-center">
                      <p className="text-sm font-medium text-[var(--text)]">Spreadsheet evidence is stored privately.</p>
                      <p className="max-w-sm text-xs leading-5 text-[var(--muted)]">Review the original XLSX separately and enter each required invoice field before preparing a posting action.</p>
                    </div>
                  )}
                  {renderBboxOverlay()}
                </div>
              </TransformComponent>
            </>
          )}
        </TransformWrapper>
      </div>
    </div>
  );
}
