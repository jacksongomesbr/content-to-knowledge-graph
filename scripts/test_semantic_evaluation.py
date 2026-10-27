import unittest
from types import SimpleNamespace
from evaluate_semantics import wilson
from generate_embeddings import chunks_for

class SemanticEvaluationTest(unittest.TestCase):
    def test_uncertainty_is_not_reported_as_perfect_certainty(self):
        low,high=wilson(51,51)
        self.assertLess(low,1);self.assertAlmostEqual(high,1)
        low,high=wilson(0,51);self.assertAlmostEqual(low,0);self.assertGreater(high,0)

    def test_model_prefix_reserves_tokens_in_every_chunk(self):
        class Tokenizer:
            def num_special_tokens_to_add(self,pair=False):return 2
            def encode(self,text,add_special_tokens=True):return list(range(len(text)+(2 if add_special_tokens else 0)))
            def __call__(self,text,**kwargs):return dict(offset_mapping=[(i,i+1) for i in range(len(text))],input_ids=list(range(len(text))))
        model=SimpleNamespace(tokenizer=Tokenizer(),max_seq_length=18)
        text='abcdefghijklmnopqrstuvwxyz';prefix='query: '
        chunks,mapping=chunks_for(model,dict(id='concept',text=text),2,prefix)
        self.assertGreater(len(chunks),1)
        for chunk,item in zip(chunks,mapping):
            self.assertLessEqual(len(model.tokenizer.encode(prefix+chunk)),model.max_seq_length)
            self.assertEqual(text[item['charStart']:item['charEnd']],chunk)
        with self.assertRaises(ValueError):chunks_for(model,dict(id='a',text=text),2,'x'*30)
