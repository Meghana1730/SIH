// Print rules for the district plan ("Download PDF" = the browser's print / Save as PDF).
// Hides the app chrome (sidebar, top bar, demo strip, breadcrumbs, toasts) and anything marked
// [data-print-hide], so only the plan document ([data-print-area]) is printed.
//
// The demo strip has no print hook of its own, so `div:has(> #main) > :not(#main)` hides every
// sibling of <main> (the top bar and the demo strip).
export const PLAN_PRINT_CSS = `
@media print {
  @page { size: A4; margin: 14mm; }
  html, body { background: #fff !important; }
  aside,
  header,
  nav[aria-label='Breadcrumb'],
  [data-print-hide],
  [data-sonner-toaster],
  div:has(> #main) > :not(#main) {
    display: none !important;
  }
  div:has(> #main) { padding-left: 0 !important; }
  #main { max-width: none !important; margin: 0 !important; padding: 0 !important; }
  [data-print-layout] { display: block !important; }
  [data-print-area] {
    border: 0 !important;
    box-shadow: none !important;
    border-radius: 0 !important;
  }
  [data-print-area] section > *,
  [data-print-area] li,
  [data-print-area] tr { break-inside: avoid; }
  [data-print-area] h2,
  [data-print-area] h3 { break-after: avoid; }
  .animate-in-up { animation: none !important; opacity: 1 !important; transform: none !important; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  a { color: inherit !important; text-decoration: none !important; }
}
`
