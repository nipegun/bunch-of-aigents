/* The API documentation page.
 *
 * The page itself is rendered by the server and needs no JavaScript. This
 * draws the sidebar, which is the layout's and not the page's - every page in
 * the frame has to ask for it, because a page is a real page here and the
 * browser threw the last one away.
 *
 * Only loaded when there is a session: an anonymous reader gets the same
 * documentation on a bare page, with no sidebar to fill in.
 */

document.addEventListener("DOMContentLoaded", function () {
  fRenderSidebar();
});
