# test faiss
import faiss
import numpy as np


def test_faiss_index():
    d = 64                           # dimension
    nb = 1000                        # database size
    nq = 10                          # number of queries

    # generate random database and query vectors
    np.random.seed(1234)             # make reproducible
    xb = np.random.random((nb, d)).astype('float32')
    xq = np.random.random((nq, d)).astype('float32')

    # build the index
    index = faiss.IndexFlatL2(d)     # build the index
    assert index.is_trained
    index.add(xb)                    # add vectors to the index
    assert index.ntotal == nb

    # perform a search
    k = 5                            # we want to see 5 nearest neighbors
    D, I = index.search(xq, k)       # actual search
    assert D.shape == (nq, k)
    assert I.shape == (nq, k)

    # check that distances are non-negative
    assert np.all(D >= 0)
    
    # check that indices are within the database size
    assert np.all(I < nb)
    # check that the nearest neighbor of a query is closer than the 5th neighbor
    for i in range(nq):
        assert D[i, 0] <= D[i, -1]
        
    # check that searching for the same vector returns itself as the nearest neighbor
    D_self, I_self = index.search(xb[:1], 1)
    assert I_self[0, 0] == 0
    assert D_self[0, 0] == 0.0
    
    # save index to disk and load it back
    faiss.write_index(index, "test_index.faiss")
    index2 = faiss.read_index("test_index.faiss")
    assert index2.ntotal == nb
    
if __name__ == "__main__":
    test_faiss_index()
    print("All FAISS tests passed.")