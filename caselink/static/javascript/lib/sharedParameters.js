//Helper for sharing some parameters between template and frontend framework
//Like common used URL, host URL, parameters in settting.py
//to avoid declearing them twice
//Need to loaded at very beginning.
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define(['exports'], function (exports) {
      factory((root.sharedParameters = exports));
    });
  } else if (typeof exports === 'object' && typeof exports.nodeName !== 'string') {
    factory(exports);
  } else {
    factory((root.sharedParameters = {}));
  }
}(this || window || {}, function (exports) {
  if(typeof window === 'object'){
    window._templateParameters = {};
    exports.set = function(name, value){
      window._templateParameters[name] = value;
    };
    exports.get = function(name){
      return window._templateParameters[name];
    };
    exports = window;
  }
  else {
    throw new Error("template-parameters doesn't support non-browser enviroment.");
  }
}));
