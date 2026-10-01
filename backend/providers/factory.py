"""Provider factory.

Maps the `provider.name` field of an agent's info.json to its adapter class.
This is the only place in the codebase that knows the full list, so adding an
eighth provider means writing its adapter file and adding one row here.

Adapter modules are imported lazily, inside the factory, so that a missing
optional SDK breaks only the agents that chose that provider instead of
preventing the whole application from starting.
"""

from backend.providers import base

# Provider name -> (module name, class name). One row per provider, matching
# the one adapter file per provider rule.
#
# Grouped by what they are rather than alphabetically, because that is the
# question being asked when this list is read: is this somebody's own hardware,
# a model built by the company serving it, or a router in front of other
# people's models?
dProviderRegistry = {
  # Model builders, serving their own models.
  "anthropic": ("anthropic", "AnthropicProvider"),
  "openai": ("openai", "OpenAiProvider"),
  "google": ("google", "GoogleProvider"),
  "deepseek": ("deepseek", "DeepSeekProvider"),
  "kimi": ("kimi", "KimiProvider"),
  "minimax": ("minimax", "MiniMaxProvider"),
  "mistral": ("mistral", "MistralProvider"),
  "qwen": ("qwen", "QwenProvider"),
  "xai": ("xai", "XaiProvider"),
  "zai": ("zai", "ZaiProvider"),
  "cohere": ("cohere", "CohereProvider"),
  "inception": ("inception", "InceptionProvider"),
  "perplexity": ("perplexity", "PerplexityProvider"),
  # Hosts and routers, serving models other people built.
  "openrouter": ("openrouter", "OpenRouterProvider"),
  "cerebras": ("cerebras", "CerebrasProvider"),
  "cloudflare": ("cloudflare", "CloudflareProvider"),
  "deepinfra": ("deepinfra", "DeepInfraProvider"),
  "fireworks": ("fireworks", "FireworksProvider"),
  "groq": ("groq", "GroqProvider"),
  "huggingface": ("huggingface", "HuggingFaceProvider"),
  "together": ("together", "TogetherProvider"),
  "vercel": ("vercel", "VercelProvider"),
  # Yours, on your own hardware.
  "ollama": ("ollama", "OllamaProvider"),
  "llamacpp": ("llamacpp", "LlamaCppProvider"),
  "vllm": ("vllm", "VllmProvider"),
}

# Other names for a provider in this list, accepted wherever one is read.
# `gemini` is what Google's own documentation calls the API; `google` is what
# every agent's info.json has said since the first version, and renaming it
# would break those files for nothing.
dProviderAliases = {
  "gemini": "google",
  "moonshot": "kimi",
  "z.ai": "zai",
  "x.ai": "xai",
  "dashscope": "qwen",
  "workers-ai": "cloudflare",
}

# Providers that need no credential, because they run on hardware you own.
lSelfHostedProviders = ["ollama", "llamacpp", "vllm"]


def fListProviderNames():
  """Return every supported provider name, in alphabetical order."""
  return sorted(dProviderRegistry.keys())


def fResolveProviderName(pProviderName):
  """Return this project's own name for a provider, following the aliases."""
  vName = str(pProviderName or "").strip().lower()
  return dProviderAliases.get(vName, vName)


def fIsSelfHosted(pProviderName):
  """Return True when the provider needs no API key."""
  return fResolveProviderName(pProviderName) in lSelfHostedProviders


def fBuildProvider(pProviderConfig, pApiKey="", pTimeoutSeconds=None):
  """Build the adapter described by one agent's provider configuration.

  pProviderConfig is the `provider` object of info.json: name, model, base_url.
  """
  dConfig = pProviderConfig or {}
  vProviderName = fResolveProviderName(dConfig.get("name"))

  if vProviderName not in dProviderRegistry:
    raise base.ProviderError(
      "Unsupported provider %r. Supported: %s"
      % (vProviderName, ", ".join(fListProviderNames()))
    )

  vModuleName, vClassName = dProviderRegistry[vProviderName]

  try:
    vModule = __import__(
      "backend.providers.%s" % (vModuleName,), fromlist=[vClassName]
    )
  except ImportError as vError:
    raise base.ProviderError(
      "Cannot load the %s adapter: %s" % (vProviderName, vError)
    )

  vProviderClass = getattr(vModule, vClassName)

  dKeywords = {
    "pModel": dConfig.get("model") or "",
    "pBaseUrl": dConfig.get("base_url") or "",
    "pApiKey": pApiKey,
    "pTimeoutSeconds": pTimeoutSeconds,
  }
  # Options that only some providers understand travel through the adapter's
  # own declaration, so the factory never grows a branch per provider.
  for vConfigKey in getattr(vProviderClass, "lExtraConfigKeys", []):
    if vConfigKey in dConfig:
      dKeywords[fConfigKeyToParameterName(vConfigKey)] = dConfig[vConfigKey]

  return vProviderClass(**dKeywords)


def fConfigKeyToParameterName(pConfigKey):
  """Turn an info.json key into its constructor parameter name.

  `reasoning_effort` becomes `pReasoningEffort`, matching the project naming
  convention for parameters.
  """
  return "p" + "".join(vPart.capitalize() for vPart in str(pConfigKey).split("_"))
