var webpack = require('webpack')
module.exports = {
  context: __dirname + "/caselink/static/javascript",
  entry: {
    // Vendors
    vendor: ['jquery', 'bootstrap-webpack', 'font-awesome-webpack', './pack/datatables.js', './pack/style.js'],
    // The script that will load before any page content loaded.
    head: './pack/pace.js',
    // Initial Script for all page.
    init: ['./pack/style.js'],
    // Page specified entry.
    a2m: './a2m.js',
    m2a: './m2a.js',
    index: './index.js',
  },
  output: {
    path: __dirname + '/caselink/static/dist/',
    publicPath: '/static/dist/',
    filename: "[name].js"
  },
  module: {
    loaders: [
      // BS FA Fonts
      { test: /\.(woff|woff2)(\?v=\d+\.\d+\.\d+)?$/, loader: 'url?limit=10000&mimetype=application/font-woff' },
      { test: /\.ttf(\?v=\d+\.\d+\.\d+)?$/, loader: 'url?limit=10000&mimetype=application/octet-stream' },
      { test: /\.eot(\?v=\d+\.\d+\.\d+)?$/, loader: 'file' },
      { test: /\.svg(\?v=\d+\.\d+\.\d+)?$/, loader: 'url?limit=10000&mimetype=image/svg+xml' },
      // Style
      { test: /\.css$/, loader: "style!css" },
      // HACK, pace-progress have a broken AMD definetion, disable "define" variable can disable AMD, force use CommonJS.
      { test: require.resolve("pace-progress"), loader: "imports?define=>false" },
    ]
  },
  plugins: [
    // ProvidePlugin make sure if "$" or "jQuery" is used in a module,
    // jquery is auto loaded as a dependency.
    // CommonChuckPlugin("vendor", ...) bundle all modules in "vendor" entry defined above
    // in a common bundle, when any of them are required, it will be imported from that bundle,
    // and HTML templates/pages should alway load this common bundle before any other
    // module may need it.
    new webpack.ProvidePlugin({
      $: "jquery",
      jQuery: "jquery",
      "window.jQuery": "jquery"
    }),
    new webpack.optimize.CommonsChunkPlugin("vendor", "vendor.bundle.js"),
  ]
};
