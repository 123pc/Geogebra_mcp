(function () {
  window.__ggbReady = false;
  window.__ggbError = null;

  function fail(message) {
    window.__ggbError = String(message || 'Unknown GeoGebra load error');
  }

  try {
    if (typeof GGBApplet === 'undefined') {
      fail('GGBApplet is not defined. GeoGebra CDN may be unreachable.');
      return;
    }

    var params = new URLSearchParams(window.location.search);
    var width = Number(params.get('width')) || 1200;
    var height = Number(params.get('height')) || 800;
    var bundle = window.__ggbBundle || params.get('bundle') || 'cdn';

    var parameters = {
      appName: 'classic',
      width: width,
      height: height,
      showToolBar: true,
      showAlgebraInput: true,
      showMenuBar: false,
      enableShiftDragZoom: true,
      useBrowserForJS: true,
      appletOnLoad: function (api) {
        window.ggbApplet = api;
        window.__ggbReady = true;
      }
    };

    var applet = new GGBApplet(parameters, true);
    if (bundle === 'local') {
      applet.setHTML5Codebase('/bundle/GeoGebra/HTML5/5.0/web3d/');
    }
    applet.inject('ggb-container');
  } catch (error) {
    fail(error && error.message ? error.message : error);
  }
}());
