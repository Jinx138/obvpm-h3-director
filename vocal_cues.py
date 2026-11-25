"""Shared English delivery vocabulary; a cue alone never authorizes dialogue."""
import re

# Explicit forms avoid accidentally matching unrelated nouns via broad stems.
_FAMILIES = (
    'say says said saying', 'speak speaks spoke spoken speaking',
    'tell tells told telling', 'utter utters uttered uttering',
    'articulate articulates articulated articulating', 'pronounce pronounces pronounced pronouncing',
    'whisper whispers whispered whispering', 'murmur murmurs murmured murmuring',
    'mumble mumbles mumbled mumbling', 'mutter mutters muttered muttering',
    'breathe breathes breathed breathing', 'shout shouts shouted shouting',
    'yell yells yelled yelling', 'scream screams screamed screaming',
    'exclaim exclaims exclaimed exclaiming', 'exclamate exclamates exclamated exclamating',
    'cry cries cried crying', 'holler hollers hollered hollering', 'bellow bellows bellowed bellowing',
    'moan moans moaned moaning', 'groan groans groaned groaning',
    'sigh sighs sighed sighing', 'gasp gasps gasped gasping', 'sob sobs sobbed sobbing',
    'whimper whimpers whimpered whimpering', 'stammer stammers stammered stammering',
    'stutter stutters stuttered stuttering', 'growl growls growled growling',
    'hiss hisses hissed hissing', 'rasp rasps rasped rasping', 'snarl snarls snarled snarling',
    'purr purrs purred purring', 'croak croaks croaked croaking',
    'ask asks asked asking', 'answer answers answered answering', 'reply replies replied replying',
    'respond responds responded responding', 'announce announces announced announcing',
    'declare declares declared declaring', 'explain explains explained explaining',
    'interrupt interrupts interrupted interrupting', 'sing sings sang sung singing',
    'chant chants chanted chanting', 'intone intones intoned intoning',
    'recite recites recited reciting', 'rap raps rapped rapping',
)
# Direct call(s) and explicit call-out phrases may introduce spoken quotes.
# Bare called/calling also introduce names and titles; keep them marker-only.
_AUTHORITY_WORDS = set(' '.join(_FAMILIES).split())
AUTHORITY_CUE = r'\b(?:call(?:s|ed|ing)?\s+out|calls?|'+ '|'.join(sorted(_AUTHORITY_WORDS, key=lambda w: (-len(w), w))) + r')\b'
_DELIVERY_PHRASE = r'deliver(?:s|ed|ing)?\s+(?:the\s+line|the\s+words|the\s+dialogue)'
VOCAL_CUE = re.compile(r'(?:\b' + _DELIVERY_PHRASE + r'\b|' + AUTHORITY_CUE + r'|\b(?:adds?|added|adding|calls?|called|calling|hums?|hummed|humming)\b)', re.I)
