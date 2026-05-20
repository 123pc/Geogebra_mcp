(function () {
  var bundle = window.__ggbBundle || 'cdn';
  var deployggbSrc = bundle === 'local'
    ? '/bundle/GeoGebra/deployggb.js'
    : 'https://www.geogebra.org/apps/deployggb.js';

  var script = document.createElement('script');
  script.src = deployggbSrc;
  script.onload = function () {
    // deployggb.js loaded — now run the runtime
    var runtimeScript = document.createElement('script');
    runtimeScript.src = './runtime.js';
    document.head.appendChild(runtimeScript);
  };
  script.onerror = function () {
    window.__ggbError = 'Failed to load deployggb.js from ' + deployggbSrc;
  };
  document.head.appendChild(script);
}());
